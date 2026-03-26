"""
Unit tests for BoundaryChecker.

Covers bounding cube computation, boundary evaluation, intersection detection,
conflicting segments discovery, and time-bound conflict filtering.
"""
# pylint: disable=protected-access  # testing critical private helpers
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from common.helpers.boundary_checker import BoundaryChecker
from common.helpers.flight_plan_engine import FlightPlanEngine
from common.models.flight_parser.enriched_flight_plan import EnrichedFlightPlan
from common.models.flight_parser.enriched_route_segment import EnrichedRouteSegment
from common.models.flight_parser.waypoint import Waypoint
from common.types.bounding_cube import BoundingCube
from common.types.conflicting_segments import ConflictingSegments


def _make_segment(
    ident: str,
    lat: float,
    lon: float,
    true_air_speed: int | None = 300,
    flight_level: int | None = 350,
) -> EnrichedRouteSegment:
    """Build an EnrichedRouteSegment for tests."""
    return EnrichedRouteSegment(
        ident=ident,
        waypoint=Waypoint(lat=lat, lon=lon),
        true_air_speed=true_air_speed,
        flight_level=flight_level,
    )

def _make_plan(segments: list[EnrichedRouteSegment]) -> EnrichedFlightPlan:
    """Build an EnrichedFlightPlan with optional config and procedures."""
    return EnrichedFlightPlan(
        config=None,
        segments=segments,
        departure_procedure="",
        arrival_procedure="",
    )

def _make_flight_adapter(
    lat: float,
    lon: float,
    speed: float,
) -> SimpleNamespace:
    """Flight-like object with speed and position for time-bound tests."""
    return SimpleNamespace(lat=lat, lon=lon, speed=speed)

# ---- _get_boundaries_of_segments ----

def test_get_boundaries_of_segments_empty_list_raises() -> None:
    """Empty segment list raises ValueError."""
    checker = BoundaryChecker(FlightPlanEngine())
    with pytest.raises(ValueError, match="At least one segment is required"):
        checker._get_boundaries_of_segments([])

def test_get_boundaries_of_segments_single_segment_returns_cube_with_margins(
) -> None:
    """Single segment yields BoundingCube with that point and half margins."""
    checker = BoundaryChecker(FlightPlanEngine())
    seg = _make_segment("A", 50.0, 14.0, 300, 350)
    cube = checker._get_boundaries_of_segments([seg])
    margin_h = BoundaryChecker.HORIZONTAL_SAFE_MARGIN / 2
    margin_v = int(BoundaryChecker.VERTICAL_SAFE_MARGIN / 2)
    assert cube.min_lat == 50.0 - margin_h
    assert cube.max_lat == 50.0 + margin_h
    assert cube.min_lon == 14.0 - margin_h
    assert cube.max_lon == 14.0 + margin_h
    assert cube.min_flight_level == 350 - margin_v
    assert cube.max_flight_level == 350 + margin_v

def test_get_boundaries_multiple_segments_min_max_with_margins() -> None:
    """Multiple segments yield min/max lat, lon, FL with half margins."""
    checker = BoundaryChecker(FlightPlanEngine())
    segs = [
        _make_segment("A", 50.0, 14.0, 300, 350),
        _make_segment("B", 52.0, 16.0, 300, 370),
        _make_segment("C", 51.0, 15.0, 300, 360),
    ]
    cube = checker._get_boundaries_of_segments(segs)
    margin_h = BoundaryChecker.HORIZONTAL_SAFE_MARGIN / 2
    margin_v = int(BoundaryChecker.VERTICAL_SAFE_MARGIN / 2)
    assert cube.min_lat == 50.0 - margin_h
    assert cube.max_lat == 52.0 + margin_h
    assert cube.min_lon == 14.0 - margin_h
    assert cube.max_lon == 16.0 + margin_h
    assert cube.min_flight_level == 350 - margin_v
    assert cube.max_flight_level == 370 + margin_v

# ---- _evaluate_boundaries ----

def test_evaluate_boundaries_overlapping_cubes_returns_true() -> None:
    """Two overlapping BoundingCubes (horizontal and vertical) return True."""
    checker = BoundaryChecker(FlightPlanEngine())
    cube1 = BoundingCube(50.0, 52.0, 14.0, 16.0, 350, 370)
    cube2 = BoundingCube(51.0, 53.0, 15.0, 17.0, 360, 380)
    assert checker._evaluate_boundaries(cube1, cube2) is True


def test_evaluate_boundaries_vertical_plan1_above_returns_false() -> None:
    """Plan1 entirely above plan2 returns False."""
    checker = BoundaryChecker(FlightPlanEngine())
    cube1 = BoundingCube(50.0, 52.0, 14.0, 16.0, 390, 410)
    cube2 = BoundingCube(51.0, 53.0, 15.0, 17.0, 350, 370)
    assert checker._evaluate_boundaries(cube1, cube2) is False

def test_evaluate_boundaries_vertical_plan1_below_returns_false() -> None:
    """Plan1 entirely below plan2 returns False."""
    checker = BoundaryChecker(FlightPlanEngine())
    cube1 = BoundingCube(50.0, 52.0, 14.0, 16.0, 330, 350)
    cube2 = BoundingCube(51.0, 53.0, 15.0, 17.0, 370, 390)
    assert checker._evaluate_boundaries(cube1, cube2) is False

def test_evaluate_boundaries_no_horizontal_overlap_plan1_left_returns_false(
) -> None:
    """Plan1 entirely to the left of plan2 returns False."""
    checker = BoundaryChecker(FlightPlanEngine())
    cube1 = BoundingCube(50.0, 52.0, 10.0, 12.0, 350, 370)
    cube2 = BoundingCube(50.0, 52.0, 14.0, 16.0, 350, 370)
    assert checker._evaluate_boundaries(cube1, cube2) is False

def test_evaluate_boundaries_no_horizontal_overlap_plan1_right_returns_false(
) -> None:
    """Plan1 entirely to the right of plan2 returns False."""
    checker = BoundaryChecker(FlightPlanEngine())
    cube1 = BoundingCube(50.0, 52.0, 18.0, 20.0, 350, 370)
    cube2 = BoundingCube(50.0, 52.0, 14.0, 16.0, 350, 370)
    assert checker._evaluate_boundaries(cube1, cube2) is False

def test_evaluate_boundaries_no_horizontal_overlap_plan1_below_returns_false(
) -> None:
    """Plan1 entirely south of plan2 (max_lat_1 < min_lat_2) returns False."""
    checker = BoundaryChecker(FlightPlanEngine())
    cube1 = BoundingCube(48.0, 49.0, 14.0, 16.0, 350, 370)
    cube2 = BoundingCube(51.0, 52.0, 14.0, 16.0, 350, 370)
    assert checker._evaluate_boundaries(cube1, cube2) is False

def test_evaluate_boundaries_no_horizontal_overlap_plan1_above_returns_false(
) -> None:
    """Plan1 entirely north of plan2 (min_lat_1 > max_lat_2) returns False."""
    checker = BoundaryChecker(FlightPlanEngine())
    cube1 = BoundingCube(53.0, 54.0, 14.0, 16.0, 350, 370)
    cube2 = BoundingCube(50.0, 51.0, 14.0, 16.0, 350, 370)
    assert checker._evaluate_boundaries(cube1, cube2) is False

def test_evaluate_boundaries_touching_boundaries_returns_true() -> None:
    """Cubes that touch at a boundary are considered intersecting."""
    checker = BoundaryChecker(FlightPlanEngine())
    cube1 = BoundingCube(50.0, 52.0, 14.0, 16.0, 350, 370)
    cube2 = BoundingCube(52.0, 54.0, 16.0, 18.0, 370, 390)
    assert checker._evaluate_boundaries(cube1, cube2) is True

# ---- has_intersection ----

def test_has_intersection_overlapping_segments_returns_true() -> None:
    """Two segment lists with overlapping bounding box and FL return True."""
    checker = BoundaryChecker(FlightPlanEngine())
    segs1 = [_make_segment("A", 50.0, 14.0), _make_segment("B", 51.0, 15.0)]
    segs2 = [_make_segment("X", 50.5, 14.5), _make_segment("Y", 51.5, 15.5)]
    assert checker.has_intersection(segs1, segs2) is True

def test_has_intersection_no_vertical_overlap_returns_false() -> None:
    """Same horizontal area but non-overlapping FL returns False."""
    checker = BoundaryChecker(FlightPlanEngine())
    segs1 = [_make_segment("A", 50.0, 14.0), _make_segment("B", 51.0, 15.0)]
    segs2 = [
        _make_segment("X", 50.5, 14.5, flight_level=390),
        _make_segment("Y", 51.0, 15.0, flight_level=390),
    ]
    assert checker.has_intersection(segs1, segs2) is False

def test_has_intersection_no_horizontal_overlap_returns_false() -> None:
    """Segments far apart in lat/lon return False."""
    checker = BoundaryChecker(FlightPlanEngine())
    segs1 = [_make_segment("A", 50.0, 14.0), _make_segment("B", 51.0, 15.0)]
    segs2 = [
        _make_segment("X", 60.0, 24.0),
        _make_segment("Y", 61.0, 25.0),
    ]
    assert checker.has_intersection(segs1, segs2) is False

def test_has_intersection_empty_segments_raises() -> None:
    """Empty segment list propagates ValueError."""
    checker = BoundaryChecker(FlightPlanEngine())
    segs = [_make_segment("A", 50.0, 14.0)]
    with pytest.raises(ValueError, match="At least one segment is required"):
        checker.has_intersection([], segs)
    with pytest.raises(ValueError, match="At least one segment is required"):
        checker.has_intersection(segs, [])

# ---- get_conflicting_segments ----

def test_get_conflicting_segments_no_overlap_returns_empty() -> None:
    """Two plans with non-overlapping routes return empty list."""
    checker = BoundaryChecker(FlightPlanEngine())
    plan1 = _make_plan([
        _make_segment("A", 50.0, 14.0),
        _make_segment("B", 51.0, 15.0),
    ])
    plan2 = _make_plan([
        _make_segment("X", 60.0, 24.0),
        _make_segment("Y", 61.0, 25.0),
    ])
    assert not checker.get_conflicting_segments(plan1, plan2)

def test_get_conflicting_segments_one_pair_returns_one_entry() -> None:
    """One overlapping segment pair returns one ConflictingSegments."""
    checker = BoundaryChecker(FlightPlanEngine())
    plan1 = _make_plan([
        _make_segment("A", 50.0, 14.0),
        _make_segment("B", 51.0, 15.0),
    ])
    plan2 = _make_plan([
        _make_segment("X", 50.5, 14.5),
        _make_segment("Y", 51.5, 15.5),
    ])
    result = checker.get_conflicting_segments(plan1, plan2)
    assert len(result) == 1
    assert result[0] == ConflictingSegments(
        flight_1_segment_start_index=0,
        flight_1_segment_end_index=1,
        flight_2_segment_start_index=0,
        flight_2_segment_end_index=1,
    )

def test_get_conflicting_segments_three_waypoints_second_overlaps() -> None:
    """Two plans, 3 waypoints each; overlap only on second segment."""
    checker = BoundaryChecker(FlightPlanEngine())
    # Plan2 first segment far, second segment overlaps plan1's second.
    plan1 = _make_plan([
        _make_segment("A", 50.0, 14.0),
        _make_segment("B", 51.0, 15.0),
        _make_segment("C", 52.0, 16.0),
    ])
    plan2 = _make_plan([
        _make_segment("X", 60.0, 24.0),
        _make_segment("Y", 51.2, 15.2),
        _make_segment("Z", 52.2, 16.2),
    ])
    result = checker.get_conflicting_segments(plan1, plan2)
    assert len(result) >= 1
    # Second segment pair is (1,2) for both plans.
    pairs = [(c.flight_1_segment_start_index, c.flight_1_segment_end_index,
              c.flight_2_segment_start_index, c.flight_2_segment_end_index)
             for c in result]
    assert (1, 2, 1, 2) in pairs

def test_get_conflicting_segments_indices_first_from_plan1() -> None:
    """Returned ConflictingSegments have first segment pair from plan 1."""
    checker = BoundaryChecker(FlightPlanEngine())
    plan1 = _make_plan([
        _make_segment("A", 50.0, 14.0),
        _make_segment("B", 51.0, 15.0),
    ])
    plan2 = _make_plan([
        _make_segment("X", 50.5, 14.5),
        _make_segment("Y", 51.0, 15.0),
    ])
    result = checker.get_conflicting_segments(plan1, plan2)
    r0 = result[0]
    assert r0.flight_1_segment_start_index <= r0.flight_1_segment_end_index
    assert r0.flight_2_segment_start_index <= r0.flight_2_segment_end_index

# ---- _evaluate_time_boundaries ----

def test_evaluate_time_boundaries_overlapping_intervals_returns_true() -> None:
    """Overlapping time windows return True."""
    checker = BoundaryChecker(FlightPlanEngine())
    assert checker._evaluate_time_boundaries(
        time_to_entry_1=0.0,
        time_to_exit_1=60.0,
        time_to_entry_2=10.0,
        time_to_exit_2=50.0,
    ) is True

def test_evaluate_time_boundaries_exit1_before_entry2_returns_false() -> None:
    """Flight1 exits before flight2 enters returns False."""
    checker = BoundaryChecker(FlightPlanEngine())
    assert checker._evaluate_time_boundaries(
        time_to_entry_1=0.0,
        time_to_exit_1=5.0,
        time_to_entry_2=10.0,
        time_to_exit_2=50.0,
    ) is False

def test_evaluate_time_boundaries_entry1_after_exit2_returns_false() -> None:
    """Flight1 enters after flight2 exits returns False."""
    checker = BoundaryChecker(FlightPlanEngine())
    assert checker._evaluate_time_boundaries(
        time_to_entry_1=60.0,
        time_to_exit_1=100.0,
        time_to_entry_2=0.0,
        time_to_exit_2=50.0,
    ) is False

# ---- get_conflict_segments_within_time_boundaries ----

def test_time_boundaries_zero_speed_raises() -> None:
    """Zero speed on flight_1 or flight_2 raises ValueError."""
    engine = FlightPlanEngine()
    checker = BoundaryChecker(engine)
    segs = [
        _make_segment("A", 50.0, 14.0),
        _make_segment("B", 51.0, 15.0),
    ]
    conflict = ConflictingSegments(0, 1, 0, 1)
    flight_ok = _make_flight_adapter(50.0, 14.0, 60.0)
    flight_zero = _make_flight_adapter(50.0, 14.0, 0.0)
    with pytest.raises(ValueError, match="Flights must have non-zero speed"):
        checker.get_conflict_segments_within_time_boundaries(
            flight_zero, flight_ok, segs, segs, [conflict]
        )
    with pytest.raises(ValueError, match="Flights must have non-zero speed"):
        checker.get_conflict_segments_within_time_boundaries(
            flight_ok, flight_zero, segs, segs, [conflict]
        )

def test_time_boundaries_overlapping_times_returns_one() -> None:
    """Mock track miles yielding overlapping times -> one result."""
    mock_engine = MagicMock(spec=FlightPlanEngine)
    # time = track_miles/speed; speed 60 -> times 0,1,10/60,50/60 overlap
    mock_engine.calculate_track_miles_to_waypoint.side_effect = [
        0.0, 60.0,  # flight_1 entry, exit
        10.0, 50.0,  # flight_2 entry, exit
    ]
    checker = BoundaryChecker(mock_engine)
    segs = [
        _make_segment("A", 50.0, 14.0),
        _make_segment("B", 51.0, 15.0),
    ]
    conflict = ConflictingSegments(0, 1, 0, 1)
    flight_1 = _make_flight_adapter(50.0, 14.0, 60.0)
    flight_2 = _make_flight_adapter(50.5, 14.5, 60.0)
    result = checker.get_conflict_segments_within_time_boundaries(
        flight_1, flight_2, segs, segs, [conflict]
    )
    assert len(result) == 1
    out = result[0]
    assert out.flight_1_segment_start_index == 0
    assert out.flight_1_segment_end_index == 1
    assert out.flight_2_segment_start_index == 0
    assert out.flight_2_segment_end_index == 1
    assert out.flight_1_segment_entry_time == 0.0
    assert out.flight_1_segment_exit_time == 1.0
    entry2 = 10.0 / 60.0
    exit2 = 50.0 / 60.0
    assert out.flight_2_segment_entry_time == pytest.approx(entry2)
    assert out.flight_2_segment_exit_time == pytest.approx(exit2)


def test_time_boundaries_non_overlapping_returns_empty() -> None:
    """When times do not overlap, result list is empty."""
    mock_engine = MagicMock(spec=FlightPlanEngine)
    # flight1: entry 0, exit 5. flight2: entry 10, exit 50 -> no overlap
    mock_engine.calculate_track_miles_to_waypoint.side_effect = [
        0.0, 300.0,   # flight_1: 0 and 5 min at 60 kt
        600.0, 3000.0,  # flight_2: 10 and 50 min at 60 kt
    ]
    checker = BoundaryChecker(mock_engine)
    segs = [
        _make_segment("A", 50.0, 14.0),
        _make_segment("B", 51.0, 15.0),
    ]
    conflict = ConflictingSegments(0, 1, 0, 1)
    flight_1 = _make_flight_adapter(50.0, 14.0, 60.0)
    flight_2 = _make_flight_adapter(50.5, 14.5, 60.0)
    result = checker.get_conflict_segments_within_time_boundaries(
        flight_1, flight_2, segs, segs, [conflict]
    )
    assert not result

def test_time_boundaries_verified_has_correct_fields() -> None:
    """Returned segment-with-time has correct indices and four times."""
    mock_engine = MagicMock(spec=FlightPlanEngine)
    mock_engine.calculate_track_miles_to_waypoint.side_effect = [
        10.0, 70.0,
        20.0, 80.0,
    ]
    checker = BoundaryChecker(mock_engine)
    segs = [
        _make_segment("A", 50.0, 14.0),
        _make_segment("B", 51.0, 15.0),
    ]
    conflict = ConflictingSegments(0, 1, 0, 1)
    flight_1 = _make_flight_adapter(50.0, 14.0, 60.0)
    flight_2 = _make_flight_adapter(50.5, 14.5, 60.0)
    result = checker.get_conflict_segments_within_time_boundaries(
        flight_1, flight_2, segs, segs, [conflict]
    )
    assert len(result) == 1
    r = result[0]
    assert hasattr(r, "flight_1_segment_entry_time")
    assert hasattr(r, "flight_1_segment_exit_time")
    assert hasattr(r, "flight_2_segment_entry_time")
    assert hasattr(r, "flight_2_segment_exit_time")
    assert r.flight_1_segment_entry_time == pytest.approx(10.0 / 60.0)
    assert r.flight_1_segment_exit_time == pytest.approx(70.0 / 60.0)
    assert r.flight_2_segment_entry_time == pytest.approx(20.0 / 60.0)
    assert r.flight_2_segment_exit_time == pytest.approx(80.0 / 60.0)
