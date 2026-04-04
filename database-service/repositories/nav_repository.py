"""Repository for navigation aid points."""

from geoalchemy2 import WKTElement
from sqlalchemy import func

from common.helpers.logging_service import LoggingService
from models import Nav
from repositories.coord_lookup_cache import CachedCoordinates, get_nav_cache
from services.database import SessionLocal

logger = LoggingService.get_logger(__name__)

class NavRepository:
    """Data access for ``nav`` table."""

    @staticmethod
    def get_closest_nav(
        lat: float,
        lon: float,
        identification: str,
    ) -> Nav | CachedCoordinates | None:
        """Finds the closest navigation waypoint to position.

        Args:
            lat: Latitude in degrees.
            lon: Longitude in degrees.
            identification: Nav identifier.

        Returns:
            ORM ``Nav`` row, cached coordinates, or None if not found.
        """
        cache = get_nav_cache()
        key = cache.make_key(lat, lon, identification)
        cached = cache.get_if_valid(key)
        if cached is not None:
            return cached

        db = SessionLocal()
        try:
            point = WKTElement(f"POINT({lon} {lat})", srid=4326)

            nav = (
                db.query(Nav)
                .filter(Nav.identificator == identification)
                .order_by(func.ST_Distance(Nav.geom, point))
                .first()
            )
            if nav is not None and nav.lat is not None and nav.lon is not None:
                cache.set_coords(key, float(nav.lat), float(nav.lon))
            return nav
        finally:
            db.close()

    @staticmethod
    def get_closest_nav_or_fail(
        lat: float,
        lon: float,
        identification: str,
    ) -> Nav | CachedCoordinates:
        """Finds the closest nav point or raises ``ValueError`` if missing."""
        nav = NavRepository.get_closest_nav(lat, lon, identification)
        if nav is None:
            raise ValueError(f"No NAV point found for {identification}, lat: {lat}, lon: {lon}")
        return nav
