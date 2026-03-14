from sqlalchemy import asc

from common.helpers.logging_service import LoggingService
from models import MTCDEvent
from services.database import SessionLocal

logger = LoggingService.get_logger(__name__)

class MtcdEventRepository:
    @staticmethod
    def get_all_for_pair(flight_id_1: str, flight_id_2: str, is_active: bool = True) -> list[MTCDEvent] | None:
        db = SessionLocal()
        try:
            mtcd_events = (
                db.query(MTCDEvent)
                .filter(
                    MTCDEvent.flight_id_1.in_([flight_id_1, flight_id_2]),
                    MTCDEvent.flight_id_2.in_([flight_id_1, flight_id_2]),
                    MTCDEvent.active == is_active,
                )
                .order_by(asc(MTCDEvent.remaining_time))
                .all()
            )
        except Exception as e:
            logger.error("Error loading MTCD events for pair of flights: %s", e, exc_info=True)
            return None
        finally:
            db.close()

        return mtcd_events