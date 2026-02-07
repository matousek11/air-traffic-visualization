from sqlalchemy import desc

from common.helpers.logging_service import LoggingService
from models import FlightPosition
from services.database import SessionLocal

logger = LoggingService.get_logger(__name__)


class FlightPositionRepository:
    @staticmethod
    def get_latest_position(flight_id: str) -> FlightPosition | None:
        """Loads newest flight position from database"""
        db = SessionLocal()
        try:
            position = (
                db.query(FlightPosition)
                .filter(FlightPosition.flight_id == flight_id)
                .order_by(desc(FlightPosition.ts))
                .first()
            )
        except Exception as e:
            logger.error(f"Error loading latest flight position: {e}", exc_info=True)
            db.rollback()
            return None
        finally:
            db.close()

        if position is None:
            return None

        if (
                position.lat is None
                or position.lon is None
                or position.flight_level is None
                or position.ground_speed_kt is None
                or position.heading is None
                or position.track_heading is None
        ):
            logger.warning(
                f"Incomplete position data for flights {flight_id}"
            )
            logger.warning(position)
            return None

        return position