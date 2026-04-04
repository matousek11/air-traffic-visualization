"""Repository for navigation fix points."""

from geoalchemy2 import WKTElement
from sqlalchemy import func

from models import Fix
from repositories.coord_lookup_cache import CachedCoordinates, get_fix_cache
from services.database import SessionLocal


class FixRepository:
    """Data access for ``fix`` table."""

    @staticmethod
    def get_closest_fix(
        lat: float,
        lon: float,
        identification: str,
    ) -> Fix | CachedCoordinates | None:
        """Finds closest fix point to position.

        Args:
            lat: Latitude in degrees.
            lon: Longitude in degrees.
            identification: Fix identifier.

        Returns:
            ORM ``Fix`` row, cached coordinates, or None if not found.
        """
        cache = get_fix_cache()
        key = cache.make_key(lat, lon, identification)
        cached = cache.get_if_valid(key)
        if cached is not None:
            return cached

        db = SessionLocal()
        try:
            point = WKTElement(f"POINT({lon} {lat})", srid=4326)

            fix = (
                db.query(Fix)
                .filter(Fix.identificator == identification)
                .order_by(func.ST_Distance(Fix.geom, point))
                .first()
            )
            if fix is not None and fix.lat is not None and fix.lon is not None:
                cache.set_coords(key, float(fix.lat), float(fix.lon))
            return fix
        finally:
            db.close()
