from geoalchemy2 import WKTElement
from sqlalchemy import func

from models import Nav
from services.database import SessionLocal


class NavRepository:
    @staticmethod
    def get_closest_nav(lat: float, lon: float, identification: str) -> Nav | None:
        """Finds closest navigation waypoint to position"""
        db = SessionLocal()
        try:
            point = WKTElement(f"POINT({lon} {lat})", srid=4326)

            nav = (
                db.query(Nav)
                .filter(Nav.identificator == identification)
                .order_by(func.ST_Distance(Nav.geom, point))
                .first()
            )
            return nav
        finally:
            db.close()

    @staticmethod
    def get_closest_nav_or_fail(lat: float, lon: float, identification: str) -> Nav:
        """Finds closest navigation waypoint to position or fail when nothing found"""
        nav = NavRepository.get_closest_nav(lat, lon, identification)
        if nav is None:
            raise ValueError(f"No NAV point found for {identification}")
        return nav