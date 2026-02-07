from geoalchemy2 import WKTElement
from sqlalchemy import func

from models import Fix
from services.database import SessionLocal


class FixRepository:
    @staticmethod
    def get_closest_fix(lat: float, lon: float, identification: str) -> Fix | None:
        """Finds closest fix point to position"""
        db = SessionLocal()
        try:
            point = WKTElement(f"POINT({lon} {lat})", srid=4326)

            fix = (
                db.query(Fix)
                .filter(Fix.identificator == identification)
                .order_by(func.ST_Distance(Fix.geom, point))
                .first()
            )
            return fix
        finally:
            db.close()