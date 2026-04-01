"""Data synchronizer for fetching flight data from flight simulation server."""

import time
import threading
from datetime import datetime, timezone
from typing import Optional

import httpx
from geoalchemy2 import WKTElement
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from common.helpers.logging_service import LoggingService
from models import Flight, FlightPosition
from services.database import SessionLocal

logger = LoggingService.get_logger(__name__)


class DataSynchronizer:
    """Synchronizes flight data from flight simulation server to database."""

    def __init__(
        self,
        api_base_url: str,
        sync_interval: float
    ):
        """
        Initialize data synchronizer.

        Args:
            api_base_url: Base URL of the flight simulation server API
            sync_interval: Interval between syncs in seconds (default: 5.0)
        """
        self.api_base_url = api_base_url
        self.sync_interval = sync_interval
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.client = httpx.Client(timeout=10.0)

    def start(self) -> None:
        """Start the synchronization thread."""
        if self.running:
            logger.warning("Synchronizer is already running")
            return

        self.running = True
        self.thread = threading.Thread(target=self._sync_loop, daemon=True)
        self.thread.start()
        logger.info(
            "Data synchronizer started (interval: %ss)",
            self.sync_interval,
        )

    def stop(self) -> None:
        """Stop the synchronization thread."""
        if not self.running:
            return

        self.running = False
        if self.thread:
            self.thread.join(timeout=10.0)
        self.client.close()
        logger.info("Data synchronizer stopped")

    def _sync_loop(self) -> None:
        """Main synchronization loop running in a separate thread."""
        while self.running:
            try:
                self._sync_flights()
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error(
                    "Error during synchronization: %s",
                    e,
                    exc_info=True,
                )

            # Sleep for sync_interval seconds
            time.sleep(self.sync_interval)

    def _sync_flights(self) -> None:
        """Fetch flights from API and sync to database."""
        try:
            response = self.client.get(f"{self.api_base_url}/flights")
            response.raise_for_status()
            flights_data = response.json()

            db: Session = SessionLocal()
            try:
                for flight_data in flights_data:
                    self._process_flight(db, flight_data)
                db.commit()
            except Exception as e:
                db.rollback()
                logger.error(
                    "Error processing flights: %s",
                    e,
                    exc_info=True,
                )
                raise
            finally:
                db.close()

        except httpx.HTTPError as e:
            logger.error("HTTP error fetching flights: %s", e)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "Unexpected error in _sync_flights: %s",
                e,
                exc_info=True,
            )

    def _process_flight(self, db: Session, flight_data: dict) -> None:
        """
        Process a single flight: create/update flight and add position.

        Args:
            db: Database session
            flight_data: Flight data from API
        """
        flight_id = flight_data["flight_id"]

        # Get or create flight
        flight = (
            db.query(Flight)
            .filter(Flight.flight_id == flight_id)
            .first()
        )
        if not flight:
            # Create new flight
            flight = Flight(
                flight_id=flight_id,
                aircraft_type=flight_data.get("plane_type"),
                origin=None,  # Not available in API
                destination=None,  # Not available in API
                active=True,
            )
            db.add(flight)
            try:
                db.flush()
                logger.info("Created new flight: %s", flight_id)
            except IntegrityError:
                # Flight might have been created by another thread
                db.rollback()
                flight = (
                    db.query(Flight)
                    .filter(Flight.flight_id == flight_id)
                    .first()
                )
                if not flight:
                    raise

        # Create flight position
        current_time = datetime.now(timezone.utc)
        lat = flight_data["lat"]
        lon = flight_data["lon"]

        # Create PostGIS POINT geometry
        geom = WKTElement(f"POINT({lon} {lat})", srid=4326)

        wind_data = flight_data.get("wind")
        wind_heading = None
        wind_speed = None
        wind_lat = None
        wind_lon = None
        wind_altitude = None
        if isinstance(wind_data, dict):
            wind_heading = wind_data.get("heading")
            wind_speed = wind_data.get("speed")
            wind_lat = wind_data.get("lat")
            wind_lon = wind_data.get("lon")
            wind_altitude = wind_data.get("altitude")

        plan_raw = flight_data.get("flight_plan")
        flight_plan_json = None
        if isinstance(plan_raw, list):
            flight_plan_json = [
                str(w["name"])
                for w in plan_raw
                if isinstance(w, dict) and w.get("name")
            ]

        flight_position = FlightPosition(
            flight_id=flight_id,
            ts=current_time,
            lat=lat,
            lon=lon,
            flight_level=flight_data.get("flight_level"),
            ground_speed_kt=flight_data.get("speed"),
            heading=flight_data.get("heading"),
            track_heading=flight_data.get("track_heading"),
            vertical_rate_fpm=int(flight_data.get("vertical_speed", 0)),
            sector_id="",  # Not available in API TODO: implement later on
            route=flight_data.get("route_string"),
            target_flight_level=flight_data.get("target_flight_level"),
            wind_heading=wind_heading,
            wind_speed=wind_speed,
            wind_lat=wind_lat,
            wind_lon=wind_lon,
            wind_altitude=wind_altitude,
            flight_plan_json=flight_plan_json,
            geom=geom,
        )

        db.add(flight_position)
        logger.debug(
            "Added position for flight %s at %s",
            flight_id,
            current_time,
        )
