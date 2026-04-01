"""Tests for FlightPositionRepository and Redis-backed latest-position cache."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from geoalchemy2 import WKTElement

from models.flight_position import FlightPosition
from repositories.flight_position_cache import (
    deserialize_flight_position,
    serialize_flight_position,
)
from repositories.flight_position_repository import FlightPositionRepository


def _geom() -> WKTElement:
    """Return WKT point for tests."""
    return WKTElement("POINT(14.0 50.0)", 4326)


def _valid_position(flight_id: str = "CSA201") -> FlightPosition:
    """Build a FlightPosition that passes repository validation."""
    return FlightPosition(
        flight_id=flight_id,
        ts=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        lat=50.0,
        lon=14.0,
        flight_level=250,
        ground_speed_kt=400,
        heading=90,
        track_heading=88,
        vertical_rate_fpm=0,
        sector_id=None,
        route="DCT",
        target_flight_level=None,
        wind_heading=None,
        wind_speed=None,
        wind_lat=None,
        wind_lon=None,
        wind_altitude=None,
        flight_plan_json=None,
        geom=_geom(),
    )


def test_serialize_deserialize_roundtrip() -> None:
    """Cached JSON round-trips to an equivalent FlightPosition."""
    original = _valid_position()
    raw = serialize_flight_position(original)
    restored = deserialize_flight_position(raw)
    assert restored is not None
    assert restored.flight_id == original.flight_id
    assert restored.lat == original.lat
    assert restored.lon == original.lon
    assert restored.flight_level == original.flight_level
    assert restored.ground_speed_kt == original.ground_speed_kt
    assert restored.track_heading == original.track_heading
    assert restored.route == original.route


def test_deserialize_invalid_json_returns_none() -> None:
    """Malformed cache payload yields None."""
    assert deserialize_flight_position("not json") is None


@patch(
    "repositories.flight_position_repository."
    "get_latest_position_cache_ttl_seconds",
    return_value=1,
)
@patch("repositories.flight_position_repository.try_cache_set")
@patch(
    "repositories.flight_position_repository.try_cache_get",
    return_value=None,
)
@patch("repositories.flight_position_repository.SessionLocal")
def test_get_latest_position_redis_miss_loads_db_and_sets_cache(
    mock_session_local: MagicMock,
    mock_try_cache_get: MagicMock,
    mock_cache_set: MagicMock,
    mock_ttl: MagicMock,
) -> None:
    """On cache miss, DB is queried and the result is written to Redis."""
    assert mock_try_cache_get.return_value is None
    assert mock_ttl.return_value == 1
    position = _valid_position()
    db = MagicMock()
    mock_session_local.return_value = db
    chain = db.query.return_value.filter.return_value.order_by.return_value
    chain.first.return_value = position

    result = FlightPositionRepository.get_latest_position("CSA201")

    assert result is position
    mock_cache_set.assert_called_once()
    call_args = mock_cache_set.call_args[0]
    assert "CSA201" in call_args[0]
    assert call_args[1] == 1
    assert isinstance(call_args[2], str)


@patch("repositories.flight_position_repository.SessionLocal")
@patch("repositories.flight_position_repository.try_cache_get")
def test_get_latest_position_redis_hit_skips_db(
    mock_cache_get: MagicMock,
    mock_session_local: MagicMock,
) -> None:
    """On cache hit, SessionLocal is not used."""
    position = _valid_position()
    mock_cache_get.return_value = serialize_flight_position(position)

    result = FlightPositionRepository.get_latest_position("CSA201")

    assert result is not None
    assert result.flight_id == "CSA201"
    mock_session_local.assert_not_called()


@patch("repositories.flight_position_repository.SessionLocal")
@patch(
    "repositories.flight_position_repository.try_cache_get",
    return_value="{}",
)
def test_get_latest_position_invalid_cache_falls_back_to_db(
    mock_bad_cache: MagicMock,
    mock_session_local: MagicMock,
) -> None:
    """Invalid cache entry causes a DB load."""
    assert mock_bad_cache.return_value == "{}"
    position = _valid_position()
    db = MagicMock()
    mock_session_local.return_value = db
    chain = db.query.return_value.filter.return_value.order_by.return_value
    chain.first.return_value = position

    result = FlightPositionRepository.get_latest_position("CSA201")

    assert result is position
    mock_session_local.assert_called_once()
