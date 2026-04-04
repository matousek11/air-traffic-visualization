#!/usr/bin/env python3
"""Handle start and stop of the worker process"""
import sys, signal

from common.helpers.logging_service import LoggingService
from services.worker import Worker

logger = LoggingService.get_logger(__name__)


def signal_handler(worker: Worker):
    """Handle shutdown signals."""
    logger.info("Shutting down worker...")
    worker.stop_consuming()
    sys.exit(0)


if __name__ == "__main__":
    worker_1 = Worker('mtcd_jobs')

    # Register signal handlers
    signal.signal(signal.SIGINT, lambda s, f: signal_handler(worker_1))
    signal.signal(signal.SIGTERM, lambda s, f: signal_handler(worker_1))

    try:
        worker_1.start_consuming()
    except Exception as e:
        logger.error("Worker error: %s", e, exc_info=True)
        sys.exit(1)