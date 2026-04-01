"""JSON serialization for caching FlightPosition rows in Redis."""

import json
from datetime import datetime

from geoalchemy2.elements import WKTElement

from common.helpers.logging_service import LoggingService
from models import FlightPosition

logger = LoggingService.get_logger(__name__)

_CACHE_KEY_PREFIX = "flight:latest_position:"


def latest_position_cache_key(flight_id: str) -> str:
    """Build Redis key for the latest position of a flight.

    Args:
        flight_id: Flight identifier.

    Returns:
        Redis key string.
    """
    return f"{_CACHE_KEY_PREFIX}{flight_id}"


def serialize_flight_position(position: FlightPosition) -> str:
    """Serialize a FlightPosition to JSON for Redis storage.

    Args:
        position: Loaded ORM instance with scalar attributes set.

    Returns:
        JSON string payload.
    """
    payload = {
        "flight_id": position.flight_id,
        "ts": position.ts.isoformat(),
        "lat": position.lat,
        "lon": position.lon,
        "flight_level": position.flight_level,
        "ground_speed_kt": position.ground_speed_kt,
        "heading": position.heading,
        "track_heading": position.track_heading,
        "vertical_rate_fpm": position.vertical_rate_fpm,
        "sector_id": position.sector_id,
        "route": position.route,
        "target_flight_level": position.target_flight_level,
        "wind_heading": position.wind_heading,
        "wind_speed": position.wind_speed,
        "wind_lat": position.wind_lat,
        "wind_lon": position.wind_lon,
        "wind_altitude": position.wind_altitude,
        "flight_plan_json": position.flight_plan_json,
    }
    return json.dumps(payload, separators=(",", ":"))


def deserialize_flight_position(raw: str) -> FlightPosition | None:
    """Deserialize JSON from Redis into a detached FlightPosition.

    Args:
        raw: JSON string from cache.

    Returns:
        FlightPosition instance, or None if data is invalid.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("Invalid flight position cache JSON: %s", exc)
        return None

    if not isinstance(data, dict):
        return None
    if not isinstance(data.get("ts"), str):
        return None

    try:
        ts = datetime.fromisoformat(data.get("ts").replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None

    lat = float(data.get("lat"))
    lon = float(data.get("lon"))
    position = FlightPosition(
        flight_id=data.get("flight_id"),
        ts=ts,
        lat=lat,
        lon=lon,
        flight_level=data.get("flight_level"),
        ground_speed_kt=data.get("ground_speed_kt"),
        heading=data.get("heading"),
        track_heading=data.get("track_heading"),
        vertical_rate_fpm=data.get("vertical_rate_fpm"),
        sector_id=data.get("sector_id"),
        route=data.get("route"),
        target_flight_level=data.get("target_flight_level"),
        wind_heading=data.get("wind_heading"),
        wind_speed=data.get("wind_speed"),
        wind_lat=data.get("wind_lat"),
        wind_lon=data.get("wind_lon"),
        wind_altitude=data.get("wind_altitude"),
        flight_plan_json=data.get("flight_plan_json"),
        geom=WKTElement(f"POINT({lon} {lat})", 4326),
    )
    return position
