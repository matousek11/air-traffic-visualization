from models import Airway
from services.database import SessionLocal


class AirwayRepository:
    @staticmethod
    def get_airway_segments(airway_id: str) -> list[Airway]:
        db = SessionLocal()
        try:
            airways = db.query(Airway).filter(
                Airway.airway_id == airway_id
            ).all()
            return airways
        finally:
            db.close()