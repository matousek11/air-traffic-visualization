"""Tests for flight snapshot mapping (BlueSky-shaped API)."""

from datetime import datetime, timezone

from geoalchemy2 import WKTElement

from models.flight import Flight
from models.flight_position import FlightPosition
from services.flight_snapshot_service import _to_detail_response, _wind_from_position


def _sample_ts() -> datetime:
    """Return fixed UTC timestamp for tests."""
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _geom() -> WKTElement:
    """Return a minimal WGS84 point for tests."""
    return WKTElement("POINT(14.0 50.0)", 4326)


def test_wind_fallback_uses_aircraft_position() -> None:
    """When wind columns are null, wind is zero at aircraft lat/lon/FL."""
    pos = FlightPosition(
        flight_id="CSA201",
        ts=_sample_ts(),
        lat=50.0,
        lon=14.0,
        flight_level=250,
        ground_speed_kt=400,
        heading=90,
        track_heading=88,
        vertical_rate_fpm=0,
        sector_id="",
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
    wind = _wind_from_position(pos)
    assert wind.heading == 0.0
    assert wind.speed == 0.0
    assert wind.lat == 50.0
    assert wind.lon == 14.0
    assert wind.altitude == 25000


def test_wind_from_stored_columns() -> None:
    """Persisted wind fields are passed through to Wind DTO."""
    pos = FlightPosition(
        flight_id="CSA201",
        ts=_sample_ts(),
        lat=50.0,
        lon=14.0,
        flight_level=250,
        ground_speed_kt=400,
        heading=90,
        track_heading=88,
        vertical_rate_fpm=0,
        sector_id="",
        route=None,
        target_flight_level=None,
        wind_heading=270.0,
        wind_speed=25.0,
        wind_lat=50.1,
        wind_lon=14.1,
        wind_altitude=26000,
        flight_plan_json=None,
        geom=_geom(),
    )
    wind = _wind_from_position(pos)
    assert wind.heading == 270.0
    assert wind.speed == 25.0
    assert wind.lat == 50.1
    assert wind.lon == 14.1
    assert wind.altitude == 26000


def test_to_detail_response_empty_flight_plan() -> None:
    """MVP maps to empty flight_plan and plane_type from aircraft_type."""
    pos = FlightPosition(
        flight_id="CSA201",
        ts=_sample_ts(),
        lat=50.0,
        lon=14.0,
        flight_level=100,
        ground_speed_kt=300,
        heading=45,
        track_heading=44,
        vertical_rate_fpm=-500,
        sector_id="",
        route="BEKVI",
        target_flight_level=120,
        wind_heading=None,
        wind_speed=None,
        wind_lat=None,
        wind_lon=None,
        wind_altitude=None,
        flight_plan_json=None,
        geom=_geom(),
    )
    flight = Flight(
        flight_id="CSA201",
        aircraft_type="B738",
        origin=None,
        destination=None,
        active=True,
    )
    detail = _to_detail_response(pos, flight)
    assert detail.flight_id == "CSA201"
    assert detail.plane_type == "B738"
    assert detail.route_string == "BEKVI"
    assert detail.flight_plan == []
    assert detail.target_flight_level == 120
    assert detail.vertical_speed == -500.0


def test_to_detail_response_with_flight_plan_json_legacy_dict() -> None:
    """Legacy dict-shaped flight_plan_json maps to waypoint name strings."""
    pos = FlightPosition(
        flight_id="CSA201",
        ts=_sample_ts(),
        lat=50.0,
        lon=14.0,
        flight_level=100,
        ground_speed_kt=300,
        heading=45,
        track_heading=44,
        vertical_rate_fpm=0,
        sector_id="",
        route="BEKVI",
        target_flight_level=None,
        wind_heading=None,
        wind_speed=None,
        wind_lat=None,
        wind_lon=None,
        wind_altitude=None,
        flight_plan_json=[
            {"name": "BEKVI", "flight_level": 250, "speed": 280},
        ],
        geom=_geom(),
    )
    flight = Flight(
        flight_id="CSA201",
        aircraft_type="B738",
        origin=None,
        destination=None,
        active=True,
    )
    detail = _to_detail_response(pos, flight)
    assert detail.flight_plan == ["BEKVI"]


def test_to_detail_response_with_flight_plan_json_string_list() -> None:
    """Current format stores ordered waypoint identifiers as strings."""
    pos = FlightPosition(
        flight_id="CSA201",
        ts=_sample_ts(),
        lat=50.0,
        lon=14.0,
        flight_level=100,
        ground_speed_kt=300,
        heading=45,
        track_heading=44,
        vertical_rate_fpm=0,
        sector_id="",
        route=None,
        target_flight_level=None,
        wind_heading=None,
        wind_speed=None,
        wind_lat=None,
        wind_lon=None,
        wind_altitude=None,
        flight_plan_json=["BEKVI", "LAM"],
        geom=_geom(),
    )
    flight = Flight(
        flight_id="CSA201",
        aircraft_type="B738",
        origin=None,
        destination=None,
        active=True,
    )
    detail = _to_detail_response(pos, flight)
    assert detail.flight_plan == ["BEKVI", "LAM"]


def test_to_detail_response_plane_type_empty_when_aircraft_type_null() -> None:
    """Null aircraft_type maps to empty plane_type string."""
    pos = FlightPosition(
        flight_id="CSA201",
        ts=_sample_ts(),
        lat=50.0,
        lon=14.0,
        flight_level=100,
        ground_speed_kt=300,
        heading=45,
        track_heading=44,
        vertical_rate_fpm=0,
        sector_id="",
        route=None,
        target_flight_level=None,
        wind_heading=None,
        wind_speed=None,
        wind_lat=None,
        wind_lon=None,
        wind_altitude=None,
        flight_plan_json=None,
        geom=_geom(),
    )
    flight = Flight(
        flight_id="CSA201",
        aircraft_type=None,
        origin=None,
        destination=None,
        active=True,
    )
    detail = _to_detail_response(pos, flight)
    assert detail.plane_type == ""
