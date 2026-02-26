"""
unit tests for PhysicsCalculator class.
"""
import math

import pytest

from common.helpers.physics_calculator import PhysicsCalculator
from common.models.position import Position

EARTH_RADIUS_KM = 6371.0
KM_PER_NAUTICAL_MILE = 1.852


# ---- get_distance_between_positions ----

def test_get_distance_between_positions_two_points() -> None:
    """Tests: haversine distance between (0°,0°) and (5°,5°) is approximately 785 km."""
    distance_km = PhysicsCalculator.get_distance_between_positions(0, 0, 5, 5)
    assert math.isclose(distance_km, 785, abs_tol=0.8)


def test_get_distance_between_positions_same_point_zero() -> None:
    """Tests: same point (identical coordinates) yields zero distance."""
    distance_km = PhysicsCalculator.get_distance_between_positions(
        50, 14, 50, 14
    )
    assert math.isclose(distance_km, 0.0, abs_tol=1e-9)


def test_get_distance_between_positions_symmetry() -> None:
    """Tests: distance is symmetric, i.e. dist(A, B) == dist(B, A)."""
    lat1, lon1 = 50.0, 14.0
    lat2, lon2 = 48.0, 17.0
    d_ab = PhysicsCalculator.get_distance_between_positions(
        lat1, lon1, lat2, lon2
    )
    d_ba = PhysicsCalculator.get_distance_between_positions(
        lat2, lon2, lat1, lon1
    )
    assert math.isclose(d_ab, d_ba, rel_tol=1e-10)


def test_get_distance_between_positions_equator_one_degree() -> None:
    """Tests: on the equator, 1 degree of longitude corresponds to approximately 111 km."""
    distance_km = PhysicsCalculator.get_distance_between_positions(0, 0, 0, 1)
    assert math.isclose(distance_km, 111, rel_tol=0.01)


# ---- get_horizontal_speed ----

def test_get_horizontal_speed_basic() -> None:
    """Tests: horizontal speed between two positions is correctly computed in km/h."""
    speed_kmh = PhysicsCalculator.get_horizontal_speed(
        Position(0, 0, 0, 240),
        Position(5, 5, 5, 240),
    )
    assert math.isclose(speed_kmh, 157, abs_tol=0.2)


def test_get_horizontal_speed_same_position_zero_speed() -> None:
    """Tests: same position with non-zero time difference yields zero speed."""
    speed_kmh = PhysicsCalculator.get_horizontal_speed(
        Position(0, 0, 0, 240),
        Position(5, 0, 0, 240),
    )
    assert math.isclose(speed_kmh, 0.0, abs_tol=1e-9)


def test_get_horizontal_speed_zero_time_raises() -> None:
    """Tests: zero time difference between positions raises ZeroDivisionError."""
    with pytest.raises(ZeroDivisionError):
        PhysicsCalculator.get_horizontal_speed(
            Position(0, 0, 0, 240),
            Position(0, 0, 0, 240),
        )


# ---- get_vertical_speed ----

def test_get_vertical_speed_descending() -> None:
    """Tests: vertical speed when descending (FL 240 to 220) in m/min."""
    vertical_speed = PhysicsCalculator.get_vertical_speed(
        Position(0, 0, 0, 240),
        Position(30, 0, 0, 220),
    )
    assert math.isclose(vertical_speed, -1219, abs_tol=1)


def test_get_vertical_speed_ascending() -> None:
    """Tests: vertical speed when ascending (FL 90 to 220) in m/min."""
    vertical_speed = PhysicsCalculator.get_vertical_speed(
        Position(0, 0, 0, 90),
        Position(30, 0, 0, 220),
    )
    assert math.isclose(vertical_speed, 7924, abs_tol=1)


def test_get_vertical_speed_same_flight_level_zero() -> None:
    """Tests: same flight level yields zero vertical speed."""
    vertical_speed = PhysicsCalculator.get_vertical_speed(
        Position(0, 0, 0, 240),
        Position(60, 10, 20, 240),
    )
    assert math.isclose(vertical_speed, 0.0, abs_tol=1e-9)


def test_get_vertical_speed_zero_time_raises() -> None:
    """Tests: zero time difference for vertical speed raises ZeroDivisionError."""
    with pytest.raises(ZeroDivisionError):
        PhysicsCalculator.get_vertical_speed(
            Position(0, 0, 0, 240),
            Position(0, 0, 0, 220),
        )


# ---- latlon_to_ecef ----

def test_latlon_to_ecef_equator_zero_fl() -> None:
    """Tests: point at equator (0°, 0°, FL 0) converts to ECEF (R, 0, 0)."""
    x, y, z = PhysicsCalculator.latlon_to_ecef(0, 0, 0)
    assert math.isclose(x, EARTH_RADIUS_KM, abs_tol=1e-6)
    assert math.isclose(y, 0.0, abs_tol=1e-6)
    assert math.isclose(z, 0.0, abs_tol=1e-6)


def test_latlon_to_ecef_north_pole() -> None:
    """Tests: north pole (90°, 0°, FL 0) has ECEF z = R, x and y zero."""
    x, y, z = PhysicsCalculator.latlon_to_ecef(90, 0, 0)
    assert math.isclose(x, 0.0, abs_tol=1e-6)
    assert math.isclose(y, 0.0, abs_tol=1e-6)
    assert math.isclose(z, EARTH_RADIUS_KM, abs_tol=1e-6)


def test_latlon_to_ecef_flight_level_increases_radius() -> None:
    """Tests: higher flight level increases ECEF vector length (radius)."""
    x0, y0, z0 = PhysicsCalculator.latlon_to_ecef(0, 0, 0)
    x100, y100, z100 = PhysicsCalculator.latlon_to_ecef(0, 0, 100)
    r0 = math.sqrt(x0 * x0 + y0 * y0 + z0 * z0)
    r100 = math.sqrt(x100 * x100 + y100 * y100 + z100 * z100)
    assert r100 > r0


# ---- ecef_to_enu ----

def test_ecef_to_enu_eastward_at_equator() -> None:
    """Tests: ECEF delta in east direction at equator yields positive east component in ENU."""
    # Small eastward move at equator: dy > 0 (ECEF), dx=dz=0
    dx, dy, dz = 0.0, 10.0, 0.0
    east, north, up = PhysicsCalculator.ecef_to_enu(dx, dy, dz, 0.0, 0.0)
    assert east > 0
    assert math.isclose(north, 0.0, abs_tol=1e-6)
    assert math.isclose(up, 0.0, abs_tol=1e-6)


def test_ecef_to_enu_round_trip_via_enu_to_latlon() -> None:
    """Tests: ENU vector from A to B, converted with enu_to_latlon from reference A, returns coordinates of B."""
    lat_a, lon_a, fl_a = 50.0, 14.0, 350
    lat_b, lon_b, fl_b = 50.1, 14.2, 360
    east, north, up = PhysicsCalculator.get_distance_vector_enu_between_positions(
        lat_a, lon_a, fl_a, lat_b, lon_b, fl_b
    )
    result = PhysicsCalculator.enu_to_latlon(
        east, north, up, lat_a, lon_a, fl_a
    )
    assert math.isclose(result.lat, lat_b, abs_tol=1e-3)
    assert math.isclose(result.lon, lon_b, abs_tol=1e-3)
    assert math.isclose(result.flight_level, fl_b, abs_tol=5)


# ---- get_distance_vector_enu_between_positions ----

def test_get_distance_vector_enu_same_position_zero() -> None:
    """Tests: same position (both points identical) yields ENU vector (0, 0, 0)."""
    east, north, up = PhysicsCalculator.get_distance_vector_enu_between_positions(
        50, 14, 300, 50, 14, 300
    )
    assert math.isclose(east, 0.0, abs_tol=1e-9)
    assert math.isclose(north, 0.0, abs_tol=1e-9)
    assert math.isclose(up, 0.0, abs_tol=1e-9)


def test_get_distance_vector_enu_same_meridian_mostly_north() -> None:
    """Tests: two points on same meridian and FL yield vector with dominant north component."""
    lat1, lon = 49.0, 14.0
    lat2 = 50.0
    fl = 350
    east, north, up = PhysicsCalculator.get_distance_vector_enu_between_positions(
        lat1, lon, fl, lat2, lon, fl
    )
    assert abs(north) > abs(east)
    assert abs(north) > abs(up)
    assert north > 0


def test_get_distance_vector_enu_magnitude_vs_haversine() -> None:
    """Tests: ENU vector magnitude (same FL) approximates haversine distance."""
    lat1, lon1 = 50.0, 14.0
    lat2, lon2 = 50.5, 14.5
    fl = 350
    east, north, up = PhysicsCalculator.get_distance_vector_enu_between_positions(
        lat1, lon1, fl, lat2, lon2, fl
    )
    magnitude_km = math.sqrt(east * east + north * north + up * up)
    haversine_km = PhysicsCalculator.get_distance_between_positions(
        lat1, lon1, lat2, lon2
    )
    assert math.isclose(magnitude_km, haversine_km, rel_tol=0.02)


# ---- enu_to_latlon ----

def test_enu_to_latlon_zero_offset_returns_ref() -> None:
    """Tests: zero offset (0, 0, 0) returns the reference point."""
    ref_lat, ref_lon, ref_fl = 50.0, 14.0, 300
    result = PhysicsCalculator.enu_to_latlon(
        0.0, 0.0, 0.0, ref_lat, ref_lon, ref_fl
    )
    assert math.isclose(result.lat, ref_lat, abs_tol=1e-9)
    assert math.isclose(result.lon, ref_lon, abs_tol=1e-9)
    assert math.isclose(result.flight_level, ref_fl, abs_tol=1e-9)


def test_enu_to_latlon_round_trip() -> None:
    """Tests: get_distance_vector_enu from A to B, then enu_to_latlon, yields B."""
    lat_a, lon_a, fl_a = 49.5, 14.2, 340
    lat_b, lon_b, fl_b = 50.2, 15.0, 380
    east, north, up = PhysicsCalculator.get_distance_vector_enu_between_positions(
        lat_a, lon_a, fl_a, lat_b, lon_b, fl_b
    )
    pos = PhysicsCalculator.enu_to_latlon(
        east, north, up, lat_a, lon_a, fl_a
    )
    assert math.isclose(pos.lat, lat_b, abs_tol=0.02)
    assert math.isclose(pos.lon, lon_b, abs_tol=0.02)
    assert math.isclose(pos.flight_level, fl_b, abs_tol=30)


# ---- km_to_nm and nm_to_km ----

def test_km_to_nm_exact() -> None:
    """Tests: 1.852 km converts to 1.0 nm; 0 km converts to 0 nm."""
    assert math.isclose(
        PhysicsCalculator.km_to_nm(KM_PER_NAUTICAL_MILE), 1.0, abs_tol=1e-9
    )
    assert math.isclose(PhysicsCalculator.km_to_nm(0.0), 0.0, abs_tol=1e-9)


def test_nm_to_km_exact() -> None:
    """Tests: 1.0 nm converts to 1.852 km."""
    assert math.isclose(
        PhysicsCalculator.nm_to_km(1.0), KM_PER_NAUTICAL_MILE, abs_tol=1e-9
    )


def test_km_to_nm_nm_to_km_round_trip() -> None:
    """Tests: round-trip km_to_nm(nm_to_km(1.0)) ≈ 1.0 and nm_to_km(km_to_nm(1.852)) ≈ 1.852."""
    assert math.isclose(
        PhysicsCalculator.km_to_nm(PhysicsCalculator.nm_to_km(1.0)),
        1.0,
        abs_tol=1e-9,
    )
    assert math.isclose(
        PhysicsCalculator.nm_to_km(PhysicsCalculator.km_to_nm(1.852)),
        1.852,
        abs_tol=1e-9,
    )
