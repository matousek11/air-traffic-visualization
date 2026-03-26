"""
Tests for MtcdToolkit (MTCD / the closest approach calculations).
"""
from dataclasses import dataclass

import numpy as np
import pytest

from common.helpers.mtcd_toolkit import MtcdToolkit
from common.models.position_3d import Position3D


@dataclass(frozen=True)
class FlightLikeForTest:
    """Flight-like object for tests (MtcdToolkit FlightLike protocol)."""
    lat: float
    lon: float
    flight_level: int
    ground_speed: int
    track_heading: int
    vertical_speed: float


# ---- get_speed_vector ----


def test_get_speed_vector_heading_north() -> None:
    """Tests: heading North: east~0, north=ground_speed, up from vertical."""
    vec = MtcdToolkit.get_speed_vector(
        ground_speed=300,
        track_heading=0,
        vertical_speed=500.0
    )
    assert np.allclose(vec[0], 0.0, atol=1e-9)
    assert np.allclose(vec[1], 300.0, atol=1e-9)
    expected_up = 500.0 * 60 / 6076.12
    assert np.allclose(vec[2], expected_up, atol=1e-6)


def test_get_speed_vector_heading_east() -> None:
    """Tests: heading 90° (East) gives north≈0, east=ground_speed."""
    vec = MtcdToolkit.get_speed_vector(
        ground_speed=400,
        track_heading=90,
        vertical_speed=0.0
    )
    assert np.allclose(vec[0], 400.0, atol=1e-9)
    assert np.allclose(vec[1], 0.0, atol=1e-9)
    assert np.allclose(vec[2], 0.0, atol=1e-9)


def test_get_speed_vector_heading_south() -> None:
    """Tests: heading 180° (South) gives east≈0, north=-ground_speed."""
    vec = MtcdToolkit.get_speed_vector(
        ground_speed=250,
        track_heading=180,
        vertical_speed=0.0
    )
    assert np.allclose(vec[0], 0.0, atol=1e-9)
    assert np.allclose(vec[1], -250.0, atol=1e-9)
    assert np.allclose(vec[2], 0.0, atol=1e-9)


def test_get_speed_vector_zero_ground_speed() -> None:
    """Tests: zero ground speed gives [0, 0, up]; up from vertical_speed."""
    vec = MtcdToolkit.get_speed_vector(
        ground_speed=0,
        track_heading=45,
        vertical_speed=1000.0
    )
    assert np.allclose(vec[0], 0.0, atol=1e-9)
    assert np.allclose(vec[1], 0.0, atol=1e-9)
    expected_up = 1000.0 * 60 / 6076.12
    assert np.allclose(vec[2], expected_up, atol=1e-6)


def test_get_speed_vector_zero_vertical_speed() -> None:
    """Tests: zero vertical speed gives third component 0."""
    vec = MtcdToolkit.get_speed_vector(
        ground_speed=350,
        track_heading=270,
        vertical_speed=0.0
    )
    assert np.allclose(vec[2], 0.0, atol=1e-9)


# ---- calculate_closest_approach_point ----


def test_calculate_closest_approach_point_none_flight_1_raises() -> None:
    """Tests: None as flight_1 raises ValueError.

    Raises:
        ValueError: When flight_1 is None.
    """
    toolkit = MtcdToolkit()
    flight2 = FlightLikeForTest(
        lat=50.0, lon=14.0, flight_level=350,
        ground_speed=400, track_heading=90, vertical_speed=0.0
    )
    msg = "Both flight objects must be provided"
    with pytest.raises(ValueError, match=msg):
        toolkit.calculate_closest_approach_point(None, flight2)  # type: ignore


def test_calculate_closest_approach_point_none_flight_2_raises() -> None:
    """Tests: None as flight_2 raises ValueError.

    Raises:
        ValueError: When flight_2 is None.
    """
    toolkit = MtcdToolkit()
    flight1 = FlightLikeForTest(
        lat=50.0, lon=14.0, flight_level=350,
        ground_speed=400, track_heading=90, vertical_speed=0.0
    )
    msg = "Both flight objects must be provided"
    with pytest.raises(ValueError, match=msg):
        toolkit.calculate_closest_approach_point(flight1, None)  # type: ignore


def test_calculate_cpa_identical_velocity_returns_none() -> None:
    """Tests: same position and velocity yields None (no unique CPA)."""
    toolkit = MtcdToolkit()
    flight = FlightLikeForTest(
        lat=50.0, lon=14.0, flight_level=350,
        ground_speed=400, track_heading=0, vertical_speed=0.0
    )
    result = toolkit.calculate_closest_approach_point(flight, flight)
    assert result is None


def test_calculate_closest_approach_point_cpa_passed_returns_none() -> None:
    """Tests: when CPA is in the past, returns None."""
    toolkit = MtcdToolkit()
    # Flight 1 east & faster; flight 2 west & slower; both east. CPA in the past.
    flight1 = FlightLikeForTest(
        lat=50.0, lon=14.05, flight_level=350,
        ground_speed=400, track_heading=90, vertical_speed=0.0
    )
    flight2 = FlightLikeForTest(
        lat=50.0, lon=13.98, flight_level=350,
        ground_speed=200, track_heading=90, vertical_speed=0.0
    )
    result = toolkit.calculate_closest_approach_point(flight1, flight2)
    assert result is None


def test_calculate_closest_approach_point_converging_returns_result() -> None:
    """Tests: two flights converging head-on return valid tuple structure."""
    toolkit = MtcdToolkit()
    flight1 = FlightLikeForTest(
        lat=50.0, lon=14.0, flight_level=350,
        ground_speed=400, track_heading=90, vertical_speed=0.0
    )
    flight2 = FlightLikeForTest(
        lat=50.0, lon=14.04, flight_level=350,
        ground_speed=400, track_heading=270, vertical_speed=0.0
    )
    result = toolkit.calculate_closest_approach_point(flight1, flight2)
    assert result is not None
    (
        horizontal_distance,
        vertical_distance,
        time_to_conflict_entry,
        time_to_conflict_exit,
        time_to_closest_approach,
        pos1_entry,
        pos1_exit,
        pos2_entry,
        pos2_exit,
        middle_point,
    ) = result
    assert time_to_closest_approach > 0
    assert horizontal_distance >= 0
    assert isinstance(vertical_distance, float)
    assert time_to_conflict_entry <= time_to_conflict_exit
    assert isinstance(pos1_entry, Position3D)
    assert isinstance(pos1_exit, Position3D)
    assert isinstance(pos2_entry, Position3D)
    assert isinstance(pos2_exit, Position3D)
    assert isinstance(middle_point, Position3D)
