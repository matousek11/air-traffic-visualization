"""Repository for loading flight positions with cache."""

from sqlalchemy import desc
from sqlalchemy.exc import SQLAlchemyError

from common.helpers.logging_service import LoggingService
from models import FlightPosition
from repositories.flight_position_cache import (
    deserialize_flight_position,
    latest_position_cache_key,
    serialize_flight_position,
)
from services.database import SessionLocal
from services.redis_client import (
    get_latest_position_cache_ttl_seconds,
    try_cache_get,
    try_cache_set,
)

logger = LoggingService.get_logger(__name__)


class FlightPositionRepository:
    """Data access for flight positions."""

    @staticmethod
    def _validate_loaded_position(
        flight_id: str,
        position: FlightPosition,
    ) -> FlightPosition | None:
        """Return position if required MTCD fields are present, else None.

        Args:
            flight_id: Expected flight id.
            position: Row loaded from DB or cache.

        Returns:
            The same position if valid; None if data is incomplete.
        """
        if (
                position.lat is None
                or position.lon is None
                or position.flight_level is None
                or position.ground_speed_kt is None
                or position.heading is None
                or position.track_heading is None
        ):
            logger.warning(
                "Incomplete position data for flight %s",
                flight_id,
            )
            logger.warning(position)
            return None
        return position

    @staticmethod
    def get_latest_position(flight_id: str) -> FlightPosition | None:
        """Loads newest flight position from cache or database.

        Args:
            flight_id: Flight identifier.

        Returns:
            Latest FlightPosition or None if not found or incomplete.
        """

        cache_key = latest_position_cache_key(flight_id)
        cached_raw = try_cache_get(cache_key)
        if cached_raw:
            cached_position = deserialize_flight_position(cached_raw)
            if cached_position is not None:
                return cached_position

        db = SessionLocal()
        try:
            position = (
                db.query(FlightPosition)
                .filter(FlightPosition.flight_id == flight_id)
                .order_by(desc(FlightPosition.ts))
                .first()
            )
        except SQLAlchemyError as exc:
            logger.error(
                "Error loading latest flight position: %s",
                exc,
                exc_info=True,
            )
            db.rollback()
            return None
        finally:
            db.close()

        if position is None:
            return None

        validated = FlightPositionRepository._validate_loaded_position(
            flight_id,
            position,
        )
        if validated is None:
            return None

        cache_key = latest_position_cache_key(flight_id)
        try:
            payload = serialize_flight_position(validated)
            try_cache_set(
                cache_key,
                get_latest_position_cache_ttl_seconds(),
                payload,
            )
        except (TypeError, ValueError) as exc:
            logger.warning(
                "Failed to serialize flight position for cache: %s",
                exc,
            )

        return validated
