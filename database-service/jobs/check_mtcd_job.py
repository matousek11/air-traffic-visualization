from datetime import datetime, timezone
from typing import Any, Dict, Tuple

from sqlalchemy import desc

from common.helpers.logging_service import LoggingService
from models import MTCDEvent, FlightPosition
from services.database import SessionLocal
from common.helpers.mtcd_toolkit import MtcdToolkit

logger = LoggingService.get_logger(__name__)

class FlightPositionAdapter:
    """Adapter to convert FlightPosition from database to Flight-like object for MtcdToolkit."""

    def __init__(self, flight_position, flight_id: str):
        """
        Initialize adapter from FlightPosition.

        Args:
            flight_position: FlightPosition object from database
            flight_id: Flight ID
        """
        self.flight_id = flight_id
        self.lat = flight_position.lat
        self.lon = flight_position.lon
        self.flight_level = flight_position.flight_level if flight_position.flight_level else 0
        self.speed = flight_position.ground_speed_kt
        self.heading = flight_position.heading
        # vertical_speed in ft/min (same as vertical_rate_fpm)
        self.vertical_speed = float(flight_position.vertical_rate_fpm or 0)

class CheckMtcdJob:
    """Job that will put new mtcd events into db or update existing one for selected flights"""
    def __init__(self) -> None:
        self.mtcd_toolkit = MtcdToolkit()

    @staticmethod
    def get_job_queue() -> str:
        return 'mtcd_jobs'

    @staticmethod
    def get_job_string() -> str:
        return 'mtcd_conflict_check'

    @staticmethod
    def format_job_data(
            flight_id_1: str,
            flight_id_2: str
    ) -> dict[str, Any]:
        return {
            "type": "mtcd_conflict_check",
            "flight_id_1": flight_id_1,
            "flight_id_2": flight_id_2,
        }

    def execute(self, job_data: Dict[str, Any]) -> bool:
        flight_id_1, flight_id_2 = self._validate_data(job_data)
        flight_1_position = self._get_newest_position(flight_id_1)
        flight_2_position = self._get_newest_position(flight_id_2)

        result = self.mtcd_toolkit.calculate_closest_approach_point(
            flight_1_position, flight_2_position
        )

        logger.info(f"Result: {result}")
        if result is None:
            # Set active MTCDs between selected pair of flights to inactive
            self._archive_mtcd(flight_id_1, flight_id_2)
            logger.info(f"Flights {flight_id_1} & {flight_id_2} doesn't have CPA or it was already passed")
            return True

        (
            horizontal_distance,
            vertical_distance,
            time_to_closest_approach,
            _, _, _
        ) = result

        if not self._is_conflict(
                horizontal_distance,
                vertical_distance,
                time_to_closest_approach
        ):
            # Set active MTCDs between selected pair of flights to inactive
            self._archive_mtcd(flight_id_1, flight_id_2)
            logger.info(f"Flights {flight_id_1} & {flight_id_2} doesn't have CPA that would trigger a conflict")
            return True

        return self._create_mtcd_event(flight_id_1, flight_id_2, result)

    def _validate_data(self, job_data: Dict[str, Any]) -> Tuple[str, str] | None:
        """Checks whether all required data are in job_data"""
        flight_id_1 = job_data.get("flight_id_1")
        flight_id_2 = job_data.get("flight_id_2")

        if flight_id_1 is None or flight_id_2 is None:
            logger.error("Missing flight IDs in job data")
            return None

        if flight_id_1 == flight_id_2:
            logger.warning(f"Same flight ID provided: {flight_id_1}")
            return None

        return flight_id_1, flight_id_2

    def _get_newest_position(self, flight_id: str) -> FlightPositionAdapter | None:
        """Loads newest position from database"""
        db = SessionLocal()
        try:
            position = (
                db.query(FlightPosition)
                .filter(FlightPosition.flight_id == flight_id)
                .order_by(desc(FlightPosition.ts))
                .first()
            )
        except Exception as e:
            logger.error(f"Error processing MTCD conflict check: {e}", exc_info=True)
            db.rollback()
            return None
        finally:
            db.close()

        if (
                position.lat is None
                or position.lon is None
                or position.flight_level is None
                or position.ground_speed_kt is None
                or position.heading is None
        ):
            logger.warning(
                f"Incomplete position data for flights {flight_id}"
            )
            logger.warning(position)
            return None

        return FlightPositionAdapter(position, flight_id)

    def _is_conflict(
            self,
            horizontal_distance: float,
            vertical_distance: float,
            time_to_closest_approach: float,
    ) -> bool:
        """Validates whether minimum distance is going to be violated"""
        # Typical separation minima: 5 NM horizontal, 1000 ft vertical
        return (
                horizontal_distance < 5.0  # 5 nautical miles
                and abs(vertical_distance) < (1000 / 6076)  # ~1000 ft in NM
                and time_to_closest_approach >= 0
        )

    def _create_mtcd_event(
            self,
            flight_id_1: str,
            flight_id_2: str,
            result: Tuple[float, float, float, float, float, float]
    ) -> bool:
        """Will create or update MTCD event connected to selected two flights"""
        (
            horizontal_distance,
            vertical_distance,
            time_to_closest_approach,
            middle_point_lat,
            middle_point_lon,
            _middle_point_fl,
        ) = result

        db = SessionLocal()
        try:
            # Check if event already exists
            existing_event = (
                db.query(MTCDEvent)
                .filter(
                    MTCDEvent.flight_id_1.in_([flight_id_1, flight_id_2]),
                    MTCDEvent.flight_id_2.in_([flight_id_1, flight_id_2]),
                    MTCDEvent.active == True,
                )
                .first()
            )

            if not existing_event:
                # Create new MTCD event
                mtcd_event = MTCDEvent(
                    flight_id_1=flight_id_1,
                    flight_id_2=flight_id_2,
                    detected_at=datetime.now(timezone.utc),
                    horizontal_distance=float(horizontal_distance),
                    vertical_distance=float(vertical_distance),
                    remaining_time=float(time_to_closest_approach),
                    middle_point_lat=float(middle_point_lat),
                    middle_point_lon=float(middle_point_lon),
                    active=True,
                    last_checked=datetime.now(timezone.utc),
                )
                db.add(mtcd_event)
                db.commit()
                logger.info(
                    f"Created MTCD event for {flight_id_1} and {flight_id_2}"
                )
            else:
                # Update existing event
                existing_event.horizontal_distance = horizontal_distance
                existing_event.vertical_distance = vertical_distance
                existing_event.remaining_time = time_to_closest_approach
                existing_event.middle_point_lat = middle_point_lat
                existing_event.middle_point_lon = middle_point_lon
                existing_event.last_checked = datetime.now(timezone.utc)
                db.commit()
                logger.debug(
                    f"Updated MTCD event for {flight_id_1} and {flight_id_2}"
                )
        except Exception as e:
            logger.error(f"Error processing MTCD conflict check: {e}", exc_info=True)
            db.rollback()
            return False
        finally:
            db.close()

        return True

    def _archive_mtcd(self, flight_id_1: str, flight_id_2: str) -> None:
        """Archive currently active MTCDs between selected pair of flights"""
        db = SessionLocal()
        try:
            # Find active MTCD events between the two flights (in either order)
            active_events = (
                db.query(MTCDEvent)
                .filter(
                    MTCDEvent.flight_id_1.in_([flight_id_1, flight_id_2]),
                    MTCDEvent.flight_id_2.in_([flight_id_1, flight_id_2]),
                    MTCDEvent.active == True,
                )
                .all()
            )

            if active_events:
                for event in active_events:
                    event.active = False
                    event.last_checked = datetime.now(timezone.utc)
                db.commit()
                logger.info(
                    f"Archived {len(active_events)} MTCD event(s) for {flight_id_1} and {flight_id_2}"
                )
        except Exception as e:
            logger.error(f"Error archiving MTCD events: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()