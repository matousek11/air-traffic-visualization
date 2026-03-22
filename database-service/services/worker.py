"""Worker for processing jobs from selected RabbitMQ queue."""

from typing import Dict, Any

from common.helpers.logging_service import LoggingService
from jobs.check_mtcd_job import CheckMtcdJob
from common.helpers.env import Env
from services.pika_client import PikaClient

logger = LoggingService.get_logger(__name__)


class Worker:
    """Worker for processing jobs from selected RabbitMQ queue."""

    def __init__(self, queue_name: str):
        """
        Initialize worker.

        Args:
            queue_name: Name of the queue
        """
        env = Env()
        self.pika_consumer = PikaClient(env, queue_name)

    def start_consuming(self):
        self.pika_consumer.start_consuming(self._handle_message)

    def stop_consuming(self):
        self.pika_consumer.stop_consuming()

    def _handle_message(
        self,
        job_data: Dict[str, Any]
    ) -> bool:
        """
        Process a job from the queue.

        Args:
            job_data: Dictionary with job data

        Returns:
            True if job was processed successfully, False otherwise
        """
        job_type = job_data.get("type")

        if job_type == "mtcd_conflict_check":
            return CheckMtcdJob().execute(job_data)
        else:
            logger.warning("Unknown job type: %s", job_type)
            return False


