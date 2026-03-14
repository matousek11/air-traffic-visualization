"""
This file contains class that handle connection to rabbitmq queue
"""
from typing import Callable, Dict, Any
import json

import pika
from pika.adapters.blocking_connection import BlockingChannel
from pika.exceptions import AMQPConnectionError
from pika.spec import Basic, BasicProperties

from common.helpers.logging_service import LoggingService
from objects.env import Env

logger = LoggingService.get_logger(__name__)

ProcessMessage = Callable[
    [BlockingChannel, Basic.Deliver, BasicProperties, bytes],
    None
]

class PikaClient:
    """
    This class handle connection to rabbitmq queue and operations with it
    """
    def __init__(self, env: Env, queue_name: str) -> None:
        self.queue_name = queue_name
        self.host = env.str("RABBITMQ_HOST")
        self.port = env.int("RABBITMQ_PORT")
        self.username = env.str("RABBITMQ_USER")
        self.password = env.str("RABBITMQ_PASS")

        self.connection: pika.BlockingConnection | None = None
        self.channel: pika.channel.Channel | None = None
        self.running = False
        self.process_message = None

        self._connect()

    def __enter__(self):
        """Context manager entry."""
        self._connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self._disconnect()

    def start_consuming(self, process_message: Any) -> None:
        """Start consuming messages from the queue."""
        self.process_message = process_message

        if not self.connection or self.connection.is_closed:
            self._connect()

        # Set QoS to process one message at a time
        self.channel.basic_qos(prefetch_count=1)

        # Start consuming
        self.channel.basic_consume(
            queue=self.queue_name, on_message_callback=self._handle_message
        )

        self.running = True
        logger.info("Worker started, waiting for messages on queue '%s'", self.queue_name)

        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, stopping worker...")
            self.stop_consuming()
            self._disconnect()

    def stop_consuming(self) -> None:
        """Stop consuming messages."""
        self.running = False
        if self.channel:
            self.channel.stop_consuming()
        logger.info("Worker stopped")

    def send_job(self, job_data: Dict[str, Any]) -> bool:
        """
        Send a job to the queue.

        Args:
            job_data: Dictionary with job data (must be JSON serializable)

        Returns:
            True if job was sent successfully, False otherwise
        """
        if not self.channel or self.channel.is_closed:
            self._connect()

        try:
            message = json.dumps(job_data)
            self.channel.basic_publish(
                exchange="",
                routing_key=self.queue_name,
                body=message,
                properties=pika.BasicProperties(
                    delivery_mode=1,
                ),
            )
            logger.debug("Sent job to queue %s: %s", self.queue_name, job_data)
            return True
        except Exception as e:
            logger.error("Failed to send job: %s", e)
            return False

    def _connect(self) -> None:
        """Establish connection to RabbitMQ."""
        try:
            credentials = pika.PlainCredentials(self.username, self.password)
            parameters = pika.ConnectionParameters(
                host=self.host,
                port=self.port,
                credentials=credentials,
            )
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            self.channel.queue_declare(queue=self.queue_name, durable=True)
            logger.info("Connected to RabbitMQ at %s:%s", self.host, self.port)
        except AMQPConnectionError as e:
            logger.error("Failed to connect to RabbitMQ: %s", e)
            raise

    def _handle_message(
        self,
        ch: pika.channel.Channel,
        method: pika.spec.Basic.Deliver,
        properties: pika.spec.BasicProperties,
        body: bytes,
    ) -> None:
        """
        Process a message from the queue.

        Args:
            ch: Channel
            method: Delivery method
            properties: Message properties
            body: Message body
        """
        try:
            job_data = json.loads(body)
            logger.info("Processing job: %s", job_data)

            success = self.process_message(job_data)

            if success:
                ch.basic_ack(delivery_tag=method.delivery_tag)
                logger.info("Job processed successfully: %s", job_data)
            else:
                # Reject and requeue on failure
                ch.basic_nack(
                    delivery_tag=method.delivery_tag, requeue=True
                )
                logger.warning("Job processing failed, requeuing: %s", job_data)

        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in message: %s", e)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        except Exception as e:
            logger.error("Error processing message: %s", e, exc_info=True)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    def _disconnect(self) -> None:
        """Close connection to RabbitMQ."""
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            logger.info("Closed RabbitMQ connection")

