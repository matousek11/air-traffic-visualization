"""
Unit tests for FlightPlanEngine.

Covers parsing/enrichment wiring, upcoming waypoint, route horizon,
track miles, flight prediction for MTCD, and edge cases.
"""
# pylint: disable=protected-access  # testing critical private helpers
import math
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from common.helpers.flight_plan_engine import FlightPlanEngine
from common.helpers.physics_calculator import PhysicsCalculator
from common.models.flight_position_adapter import FlightPositionAdapter
from common.models.flight_parser.enriched_flight_plan import EnrichedFlightPlan
from common.models.flight_parser.enriched_route_segment import EnrichedRouteSegment
from common.models.flight_parser.waypoint import Waypoint
from common.types.conflicting_segments_with_time import ConflictingSegmentWithTime


def _make_flight_adapter(
    lat: float,
    lon: float,
    speed: float,
    flight_level: int,
    vertical_speed: float = 0.0,
) -> SimpleNamespace:
    """Build a flight-like object with attributes needed by FlightPlanEngine."""
    return SimpleNamespace(
        lat=lat,
        lon=lon,
        speed=speed,
        flight_level=flight_level,
        vertical_speed=vertical_speed,
    )

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

# ---- _project_fl_at_waypoint ----

def test_project_fl_at_waypoint_small_vertical_rate_returns_current_fl() -> None:
    """Vertical speed below 100 fpm: no projection, keep current flight level."""
    out = FlightPlanEngine._project_fl_at_waypoint(
        current_fl=310,
        vertical_speed_ft_min=99.0,
        planned_fl=350,
        time_to_waypoint_h=0.5,
    )
    assert out == 310

    out_neg = FlightPlanEngine._project_fl_at_waypoint(
        current_fl=310,
        vertical_speed_ft_min=-99.0,
        planned_fl=280,
        time_to_waypoint_h=0.5,
    )
    assert out_neg == 310


def test_project_fl_at_waypoint_climbing_converging_not_yet_at_planned() -> None:
    """Climbing toward higher planned FL: return projected level if below plan."""
    # 1000 fpm -> 600 FL/h, 0.01 h -> +6 FL
    out = FlightPlanEngine._project_fl_at_waypoint(
        current_fl=300,
        vertical_speed_ft_min=1000.0,
        planned_fl=350,
        time_to_waypoint_h=0.01,
    )
    assert out == 306


def test_project_fl_at_waypoint_climbing_converging_capped_at_planned() -> None:
    """Climbing toward plan: projected above planned FL is clamped to planned."""
    # 600 FL/h * 0.2 h = +120 FL -> would overshoot 350 from 300
    out = FlightPlanEngine._project_fl_at_waypoint(
        current_fl=300,
        vertical_speed_ft_min=1000.0,
        planned_fl=350,
        time_to_waypoint_h=0.2,
    )
    assert out == 350


def test_project_fl_at_waypoint_descending_converging_above_planned() -> None:
    """Descending toward lower planned FL: projected above plan is returned."""
    # -600 FL/h * 0.01 h = -6 FL from 350 -> 344, max(344, 300)=344
    out = FlightPlanEngine._project_fl_at_waypoint(
        current_fl=350,
        vertical_speed_ft_min=-1000.0,
        planned_fl=300,
        time_to_waypoint_h=0.01,
    )
    assert out == 344


def test_project_fl_at_waypoint_descending_converging_floored_at_planned() -> None:
    """Descending toward plan: do not predict below cleared planned FL."""
    # -600 FL/h * 0.2 h = -120 FL -> 230, max(230, 300)=300
    out = FlightPlanEngine._project_fl_at_waypoint(
        current_fl=350,
        vertical_speed_ft_min=-1000.0,
        planned_fl=300,
        time_to_waypoint_h=0.2,
    )
    assert out == 300


def test_project_fl_at_waypoint_descending_planned_above_returns_kinematic() -> None:
    """Descending while planned FL is above: no clamp up to planned."""
    # -300 FL/h * 0.1 h = -30 FL -> 270
    out = FlightPlanEngine._project_fl_at_waypoint(
        current_fl=300,
        vertical_speed_ft_min=-500.0,
        planned_fl=350,
        time_to_waypoint_h=0.1,
    )
    assert out == 270


def test_project_fl_at_waypoint_climbing_planned_below_returns_kinematic() -> None:
    """Climbing while planned FL is below: no clamp down to planned."""
    # +300 FL/h * 0.1 h = +30 FL -> 380
    out = FlightPlanEngine._project_fl_at_waypoint(
        current_fl=350,
        vertical_speed_ft_min=500.0,
        planned_fl=300,
        time_to_waypoint_h=0.1,
    )
    assert out == 380


def test_project_fl_at_waypoint_exactly_hundred_fpm_projects() -> None:
    """vertical speed == 100 is not treated as small, projection applies."""
    out = FlightPlanEngine._project_fl_at_waypoint(
        current_fl=300,
        vertical_speed_ft_min=100.0,
        planned_fl=350,
        time_to_waypoint_h=0.0,
    )
    assert out == 300

# ---- _get_progress ----

def test_get_progress_same_point_a_and_b_returns_1_1() -> None:
    """Same waypoints A and B (denominator 0) return 1.1 to advance to next."""
    engine = FlightPlanEngine()
    w = Waypoint(50.0, 14.0)
    progress = engine._get_progress(50.0, 14.0, w, w)
    assert progress == 1.1

def test_get_progress_plane_at_point_a_returns_zero() -> None:
    """Plane exactly at waypoint A yields progress 0."""
    engine = FlightPlanEngine()
    a = Waypoint(50.0, 14.0)
    b = Waypoint(51.0, 15.0)
    progress = engine._get_progress(50.0, 14.0, a, b)
    assert progress == 0.0

def test_get_progress_plane_at_point_b_returns_one() -> None:
    """Plane exactly at waypoint B yields progress 1."""
    engine = FlightPlanEngine()
    a = Waypoint(50.0, 14.0)
    b = Waypoint(51.0, 15.0)
    progress = engine._get_progress(51.0, 15.0, a, b)
    assert math.isclose(progress, 1.0, abs_tol=1e-9)

def test_get_progress_plane_between_a_and_b_returns_between_zero_and_one(
) -> None:
    """Plane midway between A and B yields progress around 0.5."""
    engine = FlightPlanEngine()
    a = Waypoint(50.0, 14.0)
    b = Waypoint(52.0, 16.0)
    mid_lat, mid_lon = 51.0, 15.0
    progress = engine._get_progress(mid_lat, mid_lon, a, b)
    assert 0 < progress < 1
    assert math.isclose(progress, 0.5, abs_tol=0.1)

def test_get_progress_plane_before_a_returns_negative() -> None:
    """Plane before waypoint A yields progress < 0."""
    engine = FlightPlanEngine()
    a = Waypoint(50.0, 14.0)
    b = Waypoint(51.0, 15.0)
    progress = engine._get_progress(49.0, 13.0, a, b)
    assert progress < 0

def test_get_progress_plane_beyond_b_returns_greater_than_one() -> None:
    """Plane beyond waypoint B yields progress > 1."""
    engine = FlightPlanEngine()
    a = Waypoint(50.0, 14.0)
    b = Waypoint(51.0, 15.0)
    progress = engine._get_progress(52.0, 16.0, a, b)
    assert progress > 1.0

def test_get_progress_lateral_offset_past_b_returns_greater_than_one(
) -> None:
    """Plane past B with lateral offset due to turn toward next segment.

    Reproduces the LISBA-ABKIS bug where uncorrected lat/lon projection
    returned progress < 1.0 even though the plane had clearly passed B.
    """
    engine = FlightPlanEngine()
    a = Waypoint(50.8933, 13.7092)   # LISBA
    b = Waypoint(50.6297, 13.0572)   # ABKIS
    progress = engine._get_progress(50.33311, 13.20523, a, b)
    assert progress > 1.0

# ---- upcoming_waypoint_in_plan ----

def test_upcoming_waypoint_in_plan_single_segment_returns_zero() -> None:
    """Single segment: no segment pair, so returns last index 0."""
    engine = FlightPlanEngine()
    seg = [_make_segment("A", 50.0, 14.0)]
    plan = _make_plan(seg)
    idx = engine.upcoming_waypoint_in_plan(50.0, 14.0, plan)
    assert idx == 0

def test_upcoming_waypoint_in_plan_two_segments_plane_before_first_returns_zero(
) -> None:
    """Two segments, plane before first waypoint: returns index 0."""
    engine = FlightPlanEngine()
    segs = [
        _make_segment("A", 50.0, 14.0),
        _make_segment("B", 51.0, 15.0),
    ]
    plan = _make_plan(segs)
    idx = engine.upcoming_waypoint_in_plan(49.0, 13.0, plan)
    assert idx == 0

def test_upcoming_waypoint_in_plan_two_segments_plane_between_returns_one(
) -> None:
    """Two segments, plane between A and B: next waypoint is B (index 1)."""
    engine = FlightPlanEngine()
    segs = [
        _make_segment("A", 50.0, 14.0),
        _make_segment("B", 52.0, 16.0),
    ]
    plan = _make_plan(segs)
    idx = engine.upcoming_waypoint_in_plan(51.0, 15.0, plan)
    assert idx == 1

def test_upcoming_waypoint_in_plan_two_segments_plane_past_second_returns_last(
) -> None:
    """Two segments, plane past second waypoint: returns last index 1."""
    engine = FlightPlanEngine()
    segs = [
        _make_segment("A", 50.0, 14.0),
        _make_segment("B", 51.0, 15.0),
    ]
    plan = _make_plan(segs)
    idx = engine.upcoming_waypoint_in_plan(52.0, 16.0, plan)
    assert idx == 1

def test_upcoming_waypoint_in_plan_three_segments_plane_on_second_returns_two(
) -> None:
    """Three segments, plane on second segment: next waypoint index 2."""
    engine = FlightPlanEngine()
    segs = [
        _make_segment("A", 50.0, 14.0),
        _make_segment("B", 51.0, 15.0),
        _make_segment("C", 52.0, 16.0),
    ]
    plan = _make_plan(segs)
    idx = engine.upcoming_waypoint_in_plan(51.5, 15.5, plan)
    assert idx == 2

def test_upcoming_waypoint_in_plan_empty_segments_returns_minus_one() -> None:
    """Empty plan (no segments): range(-1) gives no iteration, returns -1."""
    engine = FlightPlanEngine()
    plan = _make_plan([])
    idx = engine.upcoming_waypoint_in_plan(50.0, 14.0, plan)
    assert idx == -1

def test_upcoming_waypoint_in_plan_lateral_offset_past_waypoint(
) -> None:
    """Plane past ABKIS with lateral offset (turning toward BALTU).

    Without longitude cosine correction the projection on segment
    LISBA->ABKIS yields progress < 1.0, incorrectly keeping ABKIS
    as the upcoming waypoint. With the fix, BALTU (index 2) is
    returned.
    """
    engine = FlightPlanEngine()
    segs = [
        _make_segment("LISBA", 50.8933, 13.7092),
        _make_segment("ABKIS", 50.6297, 13.0572),
        _make_segment("BALTU", 50.0895, 13.3265),
        _make_segment("ELMEK", 49.5500, 13.6000),
    ]
    plan = _make_plan(segs)
    idx = engine.upcoming_waypoint_in_plan(50.33311, 13.20523, plan)
    assert idx == 2, (
        f"Expected upcoming waypoint BALTU (index 2), got index {idx}"
    )

# ---- calculate_route_for_upcoming_horizon ----

def test_calculate_route_for_upcoming_horizon_first_segment_is_current_position(
) -> None:
    """Result plan's first segment is current flight position."""
    engine = FlightPlanEngine()
    flight = _make_flight_adapter(50.0, 14.0, 300.0, 350)
    segs = [
        _make_segment("A", 50.0, 14.0),
        _make_segment("B", 50.1, 14.1),
        _make_segment("C", 50.2, 14.2),
    ]
    plan = _make_plan(segs)
    result = engine.calculate_route_for_upcoming_horizon(
        0.5, flight, 0, plan
    )
    assert len(result.segments) >= 1
    first = result.segments[0]
    assert first.ident == "current_flight_pos"
    assert first.waypoint.lat == 50.0 and first.waypoint.lon == 14.0
    assert first.true_air_speed == 300.0
    assert first.flight_level == 350

def test_calculate_route_for_upcoming_horizon_zero_horizon_limits_segments(
) -> None:
    """Zero horizon: miles_threshold 0, current pos + at most one segment."""
    engine = FlightPlanEngine()
    flight = _make_flight_adapter(50.0, 14.0, 300.0, 350)
    segs = [
        _make_segment("A", 50.01, 14.01),
        _make_segment("B", 50.02, 14.02),
    ]
    plan = _make_plan(segs)
    result = engine.calculate_route_for_upcoming_horizon(
        0.0, flight, 0, plan
    )
    assert result.segments[0].ident == "current_flight_pos"
    assert len(result.segments) <= 2

def test_calculate_route_for_upcoming_horizon_large_horizon_keeps_all_segments(
) -> None:
    """Large time horizon: all segments from upcoming index remain."""
    engine = FlightPlanEngine()
    flight = _make_flight_adapter(50.0, 14.0, 300.0, 350)
    segs = [
        _make_segment("A", 50.001, 14.001),
        _make_segment("B", 50.002, 14.002),
        _make_segment("C", 50.003, 14.003),
    ]
    plan = _make_plan(segs)
    result = engine.calculate_route_for_upcoming_horizon(
        10.0, flight, 0, plan
    )
    assert result.segments[0].ident == "current_flight_pos"
    assert len(result.segments) == 4

def test_calculate_route_for_upcoming_horizon_empty_after_slice_only_prepend(
) -> None:
    """Upcoming index = segment count: empty after slice, only current pos."""
    engine = FlightPlanEngine()
    flight = _make_flight_adapter(50.0, 14.0, 300.0, 350)
    segs = [
        _make_segment("A", 50.0, 14.0),
        _make_segment("B", 51.0, 15.0),
    ]
    plan = _make_plan(segs)
    result = engine.calculate_route_for_upcoming_horizon(
        1.0, flight, 2, plan
    )
    assert len(result.segments) == 1
    assert result.segments[0].ident == "current_flight_pos"


def test_flight_levels_close() -> None:
    """Matches ``FL_LEVEL_COMPARISON_TOLERANCE`` from flight_plan_engine (see patch)."""
    close = FlightPlanEngine._flight_levels_close
    assert close(350, 350)
    assert close(350, 351)
    assert close(350, 354)
    assert not close(350, 355)
    assert not close(350, 360)


def test_calculate_route_off_profile_overrides_same_planned_step_only(
) -> None:
    """Mismatched first waypoint: override FL on all waypoints with same plan FL."""
    engine = FlightPlanEngine()
    flight = _make_flight_adapter(50.0, 14.0, 300.0, 300, vertical_speed=0.0)
    segs = [
        _make_segment("A", 50.01, 14.01, flight_level=350),
        _make_segment("B", 50.02, 14.02, flight_level=350),
        _make_segment("C", 50.03, 14.03, flight_level=350),
    ]
    plan = _make_plan(segs)
    result = engine.calculate_route_for_upcoming_horizon(10.0, flight, 0, plan)
    assert result.segments[1].flight_level == 300
    assert result.segments[2].flight_level == 300
    assert result.segments[3].flight_level == 300


def test_calculate_route_off_profile_clears_override_when_step_changes(
) -> None:
    """Different planned FL than first waypoint clears override, later steps use plan."""
    engine = FlightPlanEngine()
    flight = _make_flight_adapter(50.0, 14.0, 300.0, 300, vertical_speed=0.0)
    segs = [
        _make_segment("A", 50.01, 14.01, flight_level=350),
        _make_segment("B", 50.02, 14.02, flight_level=310),
        _make_segment("C", 50.03, 14.03, flight_level=350),
    ]
    plan = _make_plan(segs)
    result = engine.calculate_route_for_upcoming_horizon(10.0, flight, 0, plan)
    assert result.segments[1].flight_level == 300
    assert result.segments[2].flight_level == 310
    assert result.segments[3].flight_level == 350


def test_calculate_route_on_profile_respects_planned_levels_downstream(
) -> None:
    """Projected FL matches first waypoint: no override, keep enriched levels."""
    engine = FlightPlanEngine()
    flight = _make_flight_adapter(50.0, 14.0, 300.0, 350, vertical_speed=0.0)
    segs = [
        _make_segment("A", 50.01, 14.01, flight_level=350),
        _make_segment("B", 50.02, 14.02, flight_level=360),
    ]
    plan = _make_plan(segs)
    result = engine.calculate_route_for_upcoming_horizon(10.0, flight, 0, plan)
    assert result.segments[1].flight_level == 350
    assert result.segments[2].flight_level == 360

# ---- calculate_track_miles_to_waypoint ----

def test_calculate_track_miles_to_waypoint_target_first_index() -> None:
    """Target index 0: distance from flight position to first waypoint in NM."""
    engine = FlightPlanEngine()
    flight = _make_flight_adapter(50.0, 14.0, 300.0, 350)
    segs = [
        _make_segment("A", 51.0, 15.0),
        _make_segment("B", 52.0, 16.0),
    ]
    nm = engine.calculate_track_miles_to_waypoint(flight, 0, segs)
    expected_km = PhysicsCalculator.get_distance_between_positions(
        50.0, 14.0, 51.0, 15.0
    )
    expected_nm = PhysicsCalculator.km_to_nm(expected_km)
    assert math.isclose(nm, expected_nm, rel_tol=1e-6)

def test_calculate_track_miles_to_waypoint_target_last_index() -> None:
    """Target last waypoint: sum of distances along chain to target."""
    engine = FlightPlanEngine()
    flight = _make_flight_adapter(50.0, 14.0, 300.0, 350)
    segs = [
        _make_segment("A", 50.1, 14.1),
        _make_segment("B", 50.2, 14.2),
    ]
    nm = engine.calculate_track_miles_to_waypoint(flight, 1, segs)
    d1 = PhysicsCalculator.get_distance_between_positions(
        50.0, 14.0, 50.1, 14.1
    )
    d2 = PhysicsCalculator.get_distance_between_positions(
        50.1, 14.1, 50.2, 14.2
    )
    expected_nm = PhysicsCalculator.km_to_nm(d1 + d2)
    assert math.isclose(nm, expected_nm, rel_tol=1e-6)

def test_calculate_track_miles_to_waypoint_target_beyond_end_returns_total(
) -> None:
    """Target index beyond segment count: returns total track miles."""
    engine = FlightPlanEngine()
    flight = _make_flight_adapter(50.0, 14.0, 300.0, 350)
    segs = [
        _make_segment("A", 50.1, 14.1),
        _make_segment("B", 50.2, 14.2),
    ]
    nm = engine.calculate_track_miles_to_waypoint(flight, 99, segs)
    d1 = PhysicsCalculator.get_distance_between_positions(
        50.0, 14.0, 50.1, 14.1
    )
    d2 = PhysicsCalculator.get_distance_between_positions(
        50.1, 14.1, 50.2, 14.2
    )
    expected_nm = PhysicsCalculator.km_to_nm(d1 + d2)
    assert math.isclose(nm, expected_nm, rel_tol=1e-6)

def test_calculate_track_miles_to_waypoint_single_segment_index_zero() -> None:
    """Single segment, target index 0: one leg flight to segment[0].waypoint."""
    engine = FlightPlanEngine()
    flight = _make_flight_adapter(0.0, 0.0, 300.0, 350)
    segs = [_make_segment("A", 1.0, 1.0)]
    nm = engine.calculate_track_miles_to_waypoint(flight, 0, segs)
    expected_km = PhysicsCalculator.get_distance_between_positions(
        0.0, 0.0, 1.0, 1.0
    )
    expected_nm = PhysicsCalculator.km_to_nm(expected_km)
    assert math.isclose(nm, expected_nm, rel_tol=1e-6)

# ---- get_flight_prediction_for_segments ----

def test_get_flight_prediction_for_segments_returns_flight_like_and_horizon(
) -> None:
    """Returns two FlightLike and mtcd_horizon; horizon = exit - entry."""
    engine = FlightPlanEngine()
    segs_1 = [
        _make_segment("A1", 50.0, 14.0),
        _make_segment("B1", 51.0, 15.0),
    ]
    segs_2 = [
        _make_segment("A2", 50.5, 14.5),
        _make_segment("B2", 51.5, 15.5),
    ]
    conf = ConflictingSegmentWithTime(
        flight_1_segment_start_index=0,
        flight_1_segment_end_index=1,
        flight_2_segment_start_index=0,
        flight_2_segment_end_index=1,
        flight_1_segment_entry_time=0.0,
        flight_1_segment_exit_time=60.0,
        flight_2_segment_entry_time=10.0,
        flight_2_segment_exit_time=50.0,
    )
    f1, f2, horizon, _, _ = engine.get_flight_prediction_for_segments(
        segs_1, segs_2, conf
    )
    assert hasattr(f1, "lat") and hasattr(f1, "lon")
    assert hasattr(f1, "flight_level") and hasattr(f1, "ground_speed")
    assert hasattr(f1, "track_heading") and hasattr(f1, "vertical_speed")
    assert hasattr(f2, "lat") and hasattr(f2, "lon")
    segment_entry = max(
        conf.flight_1_segment_entry_time, conf.flight_2_segment_entry_time
    )
    segment_exit = min(
        conf.flight_1_segment_exit_time, conf.flight_2_segment_exit_time
    )
    expected_horizon = segment_exit - segment_entry
    assert math.isclose(horizon, expected_horizon, abs_tol=1e-9)

def test_get_flight_prediction_for_segments_zero_duration_raises() -> None:
    """When segment duration is zero or negative, ValueError raised."""
    engine = FlightPlanEngine()
    segs = [
        _make_segment("A", 50.0, 14.0),
        _make_segment("B", 51.0, 15.0),
    ]
    conf = ConflictingSegmentWithTime(
        flight_1_segment_start_index=0,
        flight_1_segment_end_index=1,
        flight_2_segment_start_index=0,
        flight_2_segment_end_index=1,
        flight_1_segment_entry_time=10.0,
        flight_1_segment_exit_time=9.0,
        flight_2_segment_entry_time=0.0,
        flight_2_segment_exit_time=60.0,
    )
    with pytest.raises(
        ValueError, match="Duration of segment should be positive"
    ):
        engine.get_flight_prediction_for_segments(segs, segs, conf)

def test_get_flight_prediction_for_segments_interpolation_at_entry() -> None:
    """segment_entry_time = flight entry_time -> t=0 -> position at start."""
    engine = FlightPlanEngine()
    segs = [
        _make_segment("S", 50.0, 14.0),
        _make_segment("E", 51.0, 15.0),
    ]
    conf = ConflictingSegmentWithTime(
        flight_1_segment_start_index=0,
        flight_1_segment_end_index=1,
        flight_2_segment_start_index=0,
        flight_2_segment_end_index=1,
        flight_1_segment_entry_time=0.0,
        flight_1_segment_exit_time=60.0,
        flight_2_segment_entry_time=0.0,
        flight_2_segment_exit_time=60.0,
    )
    f1, _, _, _, _ = engine.get_flight_prediction_for_segments(segs, segs, conf)
    assert math.isclose(f1.lat, 50.0, abs_tol=1e-6)
    assert math.isclose(f1.lon, 14.0, abs_tol=1e-6)

# ---- extrapolate_along_route_by_time ----

def test_extrapolate_along_route_by_time_mid_first_leg() -> None:
    """Half of first leg at constant GS lands at the segment midpoint."""
    engine = FlightPlanEngine()
    segs = [
        _make_segment("A", 52.0, 16.0, flight_level=280),
        _make_segment("B", 53.0, 17.0, flight_level=290),
    ]
    plan = _make_plan(segs)
    flight = SimpleNamespace(
        ts=None,
        lat=50.0,
        lon=14.0,
        flight_level=280,
        ground_speed_kt=60.0,
        heading=0,
        track_heading=0,
        route="R",
        vertical_rate_fpm=0,
    )
    adapter = FlightPositionAdapter(flight, "X")
    leg_km = PhysicsCalculator.get_distance_between_positions(
        50.0,
        14.0,
        52.0,
        16.0,
    )
    leg_nm = PhysicsCalculator.km_to_nm(leg_km)
    elapsed_hours = (leg_nm / 2.0) / 60.0
    out = engine.extrapolate_along_route_by_time(
        adapter,
        plan,
        0,
        elapsed_hours,
    )
    assert math.isclose(out.lat, 51.0, abs_tol=1e-5)
    assert math.isclose(out.lon, 15.0, abs_tol=1e-5)

def test_extrapolate_along_route_by_time_zero_elapsed_unchanged() -> None:
    """Non-positive elapsed time returns a copy with the same coordinates."""
    engine = FlightPlanEngine()
    segs = [_make_segment("A", 52.0, 16.0)]
    plan = _make_plan(segs)
    flight = SimpleNamespace(
        ts=None,
        lat=50.0,
        lon=14.0,
        flight_level=280,
        ground_speed_kt=60.0,
        heading=0,
        track_heading=0,
        route="R",
        vertical_rate_fpm=0,
    )
    adapter = FlightPositionAdapter(flight, "X")
    out = engine.extrapolate_along_route_by_time(adapter, plan, 0, 0.0)
    assert out.lat == adapter.lat
    assert out.lon == adapter.lon

# ---- _prepend_current_position ----

def test_prepend_current_position_adds_first_segment_with_flight_data(
) -> None:
    """First segment is current_flight_pos with flight lat, lon, speed, FL."""
    engine = FlightPlanEngine()
    flight = _make_flight_adapter(50.123, 14.456, 280.0, 340)
    segs = [
        _make_segment("A", 51.0, 15.0),
        _make_segment("B", 52.0, 16.0),
    ]
    plan = _make_plan(segs)
    result = engine._prepend_current_position(plan, flight)
    assert len(result.segments) == 3
    first = result.segments[0]
    assert first.ident == "current_flight_pos"
    assert first.waypoint.lat == 50.123
    assert first.waypoint.lon == 14.456
    assert first.true_air_speed == 280.0
    assert first.flight_level == 340
    assert result.segments[1].ident == "A"
    assert result.segments[2].ident == "B"

def test_prepend_current_position_empty_plan_yields_one_segment() -> None:
    """Empty plan: after prepend only one segment (current position)."""
    engine = FlightPlanEngine()
    flight = _make_flight_adapter(50.0, 14.0, 300.0, 350)
    plan = _make_plan([])
    result = engine._prepend_current_position(plan, flight)
    assert len(result.segments) == 1
    assert result.segments[0].ident == "current_flight_pos"

# ---- process_flight_plan (mocked) ----

@patch("common.helpers.flight_plan_engine.FlightPositionRepository")
@patch("common.helpers.flight_plan_engine.RouteEnricher")
@patch("common.helpers.flight_plan_engine.RouteParser")
def test_process_flight_plan_calls_parser_repo_enricher_returns_enriched(
    mock_parser_class: MagicMock,
    mock_enricher_class: MagicMock,
    mock_repo: MagicMock,
) -> None:
    """Calls get_latest_position, parse, enrich; returns enriched plan."""
    mock_parser = MagicMock()
    mock_parser_class.return_value = mock_parser
    mock_enricher = MagicMock()
    mock_enricher_class.return_value = mock_enricher

    parsed = MagicMock()
    mock_parser.parse.return_value = parsed
    flight_pos = MagicMock()
    mock_repo.get_latest_position.return_value = flight_pos

    expected_plan = _make_plan([_make_segment("X", 50.0, 14.0)])
    mock_enricher.enrich.return_value = expected_plan

    engine = FlightPlanEngine()
    engine.parser = mock_parser
    engine.enricher = mock_enricher

    result = engine.process_flight_plan("CSA201", "DENUT L610 LAM")

    mock_parser.parse.assert_called_once_with("DENUT L610 LAM")
    mock_repo.get_latest_position.assert_called_once_with("CSA201")
    mock_enricher.enrich.assert_called_once_with(flight_pos, parsed)
    assert result == expected_plan


@patch("common.helpers.flight_plan_engine.time.monotonic", side_effect=[0.0, 0.0, 10.0])
@patch("common.helpers.flight_plan_engine.FlightPositionRepository")
@patch("common.helpers.flight_plan_engine.RouteEnricher")
@patch("common.helpers.flight_plan_engine.RouteParser")
def test_process_flight_plan_cache_hit_skips_parse_and_enrich(
    mock_parser_class: MagicMock,
    mock_enricher_class: MagicMock,
    mock_repo: MagicMock,
    _mock_mono: MagicMock,
) -> None:
    """Second call within TTL returns cached plan without parse or enrich."""
    mock_parser = MagicMock()
    mock_parser_class.return_value = mock_parser
    mock_enricher = MagicMock()
    mock_enricher_class.return_value = mock_enricher

    parsed = MagicMock()
    mock_parser.parse.return_value = parsed
    flight_pos = MagicMock()
    mock_repo.get_latest_position.return_value = flight_pos

    expected_plan = _make_plan([_make_segment("X", 50.0, 14.0)])
    mock_enricher.enrich.return_value = expected_plan

    engine = FlightPlanEngine()
    engine.parser = mock_parser
    engine.enricher = mock_enricher

    engine.process_flight_plan("CSA201", "DENUT L610 LAM")
    engine.process_flight_plan("CSA201", "OTHER ROUTE")

    mock_parser.parse.assert_called_once()
    mock_enricher.enrich.assert_called_once()


@patch("common.helpers.flight_plan_engine.time.monotonic", side_effect=[0.0, 0.0, 31.0, 31.0])
@patch("common.helpers.flight_plan_engine.FlightPositionRepository")
@patch("common.helpers.flight_plan_engine.RouteEnricher")
@patch("common.helpers.flight_plan_engine.RouteParser")
def test_process_flight_plan_cache_expires_after_ttl(
    mock_parser_class: MagicMock,
    mock_enricher_class: MagicMock,
    mock_repo: MagicMock,
    _mock_mono: MagicMock,
) -> None:
    """After TTL seconds, parse and enrich run again."""
    mock_parser = MagicMock()
    mock_parser_class.return_value = mock_parser
    mock_enricher = MagicMock()
    mock_enricher_class.return_value = mock_enricher

    parsed = MagicMock()
    mock_parser.parse.return_value = parsed
    flight_pos = MagicMock()
    mock_repo.get_latest_position.return_value = flight_pos

    expected_plan = _make_plan([_make_segment("X", 50.0, 14.0)])
    mock_enricher.enrich.return_value = expected_plan

    engine = FlightPlanEngine()
    engine.parser = mock_parser
    engine.enricher = mock_enricher

    engine.process_flight_plan("CSA201", "DENUT L610 LAM")
    engine.process_flight_plan("CSA201", "DENUT L610 LAM")

    assert mock_parser.parse.call_count == 2
    assert mock_enricher.enrich.call_count == 2
