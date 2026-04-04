#!/usr/bin/env python3
"""Script to run MTCD event check and send jobs to the queue for conflict detection."""

import json
import time
from typing import Dict, List, Tuple

from common.helpers.logging_service import LoggingService
from jobs.check_mtcd_job import CheckMtcdJob
from common.helpers.env import Env
from services.mtcd_event_check import MTCDEventCheck
from services.pika_client import PikaClient

BATCH_SIZE = 100
logger = LoggingService.get_logger(__name__)


def create_detection_jobs(conflicts: Dict[str, List[str]]) -> Tuple[int, int]:
    """
    Send MTCD detection jobs to queue for processing.

    Args:
        conflicts: Dictionary mapping flight_id to list of conflicting flight_ids

    Returns:
        Tuple of (jobs_sent, jobs_failed)
    """
    if not conflicts:
        logger.info("No potential conflicts found, no jobs to send")
        return 0, 0

    pairs_sent = 0
    jobs_sent = 0
    jobs_failed = 0

    with PikaClient(Env(), CheckMtcdJob.get_job_queue()) as queue:
        pairs_to_send = []
        for flight_id_1, conflicting_flights in conflicts.items():
            for flight_id_2 in conflicting_flights:
                pairs_to_send.append(CheckMtcdJob.format_job_data(flight_id_1, flight_id_2))
                pairs_sent += 1

        for i in range(0, len(pairs_to_send), BATCH_SIZE):
            batch = pairs_to_send[i: i + BATCH_SIZE]
            success = queue.send_job(
                CheckMtcdJob.format_multiple_jobs(batch)
            )
            if success:
                jobs_sent += 1
                logger.debug("Sent detection jobs: %s", batch)
            else:
                jobs_failed += 1
                logger.warning("Failed to send jobs: %s", batch)

    logger.info("Sent %s detection jobs to queue '%s'", pairs_sent, CheckMtcdJob.get_job_queue())
    if jobs_failed > 0:
        logger.warning("Failed to send %s jobs", jobs_failed)

    return jobs_sent, jobs_failed


if __name__ == "__main__":
    logger.info("Starting MTCD event check loop (Ctrl+C to stop)...")
    
    try:
        while True:
            potential_conflicts = MTCDEventCheck(0.25).find_potential_conflicts()
            print(json.dumps(potential_conflicts, indent=2))

            create_detection_jobs(potential_conflicts)
            
            time.sleep(40)
    except KeyboardInterrupt:
        logger.info("Stopped by user (Ctrl+C)")
        print("\nStopped.")
