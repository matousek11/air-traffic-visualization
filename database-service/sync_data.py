#!/usr/bin/env python3
"""Main script to run the data synchronizer."""

import signal
import sys

from common.helpers.logging_service import LoggingService
from services.data_synchronizer import DataSynchronizer
from objects.env import Env

logging = LoggingService.get_logger(__name__)

env = Env()

# Get configuration from environment
api_base_url = env.str("FLIGHT_SIMULATION_API_URL", "http://localhost:8001")
sync_interval = env.int("SYNC_INTERVAL", 5)

# Create and start synchronizer
synchronizer = DataSynchronizer(
    api_base_url=api_base_url,
    sync_interval=float(sync_interval),
)


def signal_handler(sig, frame):
    """Handle shutdown signals."""
    logging.info("Shutting down synchronizer...")
    synchronizer.stop()
    sys.exit(0)


# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if __name__ == "__main__":
    logging.info(f"Starting data synchronizer (API: {api_base_url}, interval: {sync_interval}s)")
    synchronizer.start()

    try:
        # Keep main thread alive
        while True:
            signal.pause()
    except KeyboardInterrupt:
        signal_handler(None, None)
