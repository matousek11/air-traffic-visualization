"""
Unit tests for RouteEnricher.

Covers enrich (config, DCT, airway, errors), get_point (Fix/Nav fallback),
get_airway_waypoints, and _get_points_to_end_waypoint.
"""
# pylint: disable=protected-access  # testing critical private helpers
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from common.helpers.route_enricher import RouteEnricher
from common.models.flight_parser.enriched_flight_plan import EnrichedFlightPlan
from common.models.flight_parser.enriched_route_segment import EnrichedRouteSegment
from common.models.flight_parser.initial_route_config import InitialRouteConfig
from common.models.flight_parser.parsed_flight_plan import ParsedFlightPlan
from common.models.flight_parser.raw_route_segment import RawRouteSegment
from common.models.flight_parser.waypoint import Waypoint


def _make_flight_position(
    lat: float = 50.0,
    lon: float = 14.0,
    ground_speed_kt: int = 450,
    flight_level: int = 350,
) -> SimpleNamespace:
    """Build a flight position-like object for tests.

    Args:
        lat: Latitude.
        lon: Longitude.
        ground_speed_kt: Ground speed in knots.
        flight_level: Flight level.

    Returns:
        SimpleNamespace with attributes used by RouteEnricher.
    """
    return SimpleNamespace(
        lat=lat,
        lon=lon,
        ground_speed_kt=ground_speed_kt,
        flight_level=flight_level,
    )

def _make_point(lat: float, lon: float) -> SimpleNamespace:
    """Build a Fix/Nav-like object with lat and lon.

    Args:
        lat: Latitude.
        lon: Longitude.

    Returns:
        SimpleNamespace with lat, lon.
    """
    return SimpleNamespace(lat=lat, lon=lon)

def _make_raw_segment(
    ident: str,
    via_airway: str | None = None,
    true_air_speed: int | None = None,
    flight_level: int | None = None,
) -> RawRouteSegment:
    """Build a RawRouteSegment for tests.

    Args:
        ident: Waypoint identifier.
        via_airway: Airway name or None/DCT.
        true_air_speed: Optional TAS.
        flight_level: Optional FL.

    Returns:
        RawRouteSegment instance.
    """
    return RawRouteSegment(
        ident=ident,
        via_airway=via_airway,
        true_air_speed=true_air_speed,
        flight_level=flight_level,
    )

def _make_parsed_plan(
    segments: list[RawRouteSegment],
    config: InitialRouteConfig | None = None,
    departure_procedure: str = "",
    arrival_procedure: str = "",
) -> ParsedFlightPlan:
    """Build a ParsedFlightPlan for tests.

    Args:
        segments: List of raw route segments.
        config: Optional initial route config.
        departure_procedure: Departure procedure string.
        arrival_procedure: Arrival procedure string.

    Returns:
        ParsedFlightPlan instance.
    """
    return ParsedFlightPlan(
        config=config,
        segments=segments,
        departure_procedure=departure_procedure,
        arrival_procedure=arrival_procedure,
    )

def _make_airway_mock(
    start_waypoint: str,
    end_waypoint: str,
    start_lat: float = 50.0,
    start_lon: float = 14.0,
    airway_id: str = "L610",
) -> MagicMock:
    """Build an Airway-like mock with get_next_point.

    Args:
        start_waypoint: Start waypoint id.
        end_waypoint: End waypoint id.
        start_lat: Start latitude.
        start_lon: Start longitude.
        airway_id: Airway identifier.

    Returns:
        MagicMock with start_waypoint, end_waypoint, start_lat, start_lon,
        airway_id, and get_next_point(current) returning the other end.
    """
    seg = MagicMock()
    seg.start_waypoint = start_waypoint
    seg.end_waypoint = end_waypoint
    seg.start_lat = start_lat
    seg.start_lon = start_lon
    seg.airway_id = airway_id

    def get_next(current: str) -> str:
        if current == start_waypoint:
            return end_waypoint
        return start_waypoint

    seg.get_next_point.side_effect = get_next
    return seg

# ---- enrich ----

@patch("common.helpers.route_enricher.NavRepository")
@patch("common.helpers.route_enricher.FixRepository")
def test_enrich_no_config_uses_flight_position_speed_and_fl(
    mock_fix_repo: MagicMock,
    mock_nav_repo: MagicMock,
) -> None:
    """When config is None, ground_speed_kt and flight_level from position are used."""
    mock_fix_repo.get_closest_fix.return_value = _make_point(50.1, 14.1)
    flight_pos = _make_flight_position(ground_speed_kt=420, flight_level=380)
    segments = [_make_raw_segment("BALTU", via_airway=None)]
    plan = _make_parsed_plan(segments, config=None)

    enricher = RouteEnricher()
    result = enricher.enrich(flight_pos, plan)

    assert result.config is None
    assert len(result.segments) == 1
    assert result.segments[0].ident == "BALTU"
    assert result.segments[0].true_air_speed == 420
    assert result.segments[0].flight_level == 380

@patch("common.helpers.route_enricher.NavRepository")
@patch("common.helpers.route_enricher.FixRepository")
def test_enrich_with_config_uses_config_speed_and_fl(
    mock_fix_repo: MagicMock,
    mock_nav_repo: MagicMock,
) -> None:
    """When config is set, config true_air_speed and flight_level are used."""
    mock_fix_repo.get_closest_fix.return_value = _make_point(50.1, 14.1)
    flight_pos = _make_flight_position()
    config = InitialRouteConfig(raw="N0450F310", true_air_speed=450, flight_level=310)
    segments = [_make_raw_segment("X", via_airway=None)]
    plan = _make_parsed_plan(segments, config=config)

    enricher = RouteEnricher()
    result = enricher.enrich(flight_pos, plan)

    assert result.segments[0].true_air_speed == 450
    assert result.segments[0].flight_level == 310

@patch("common.helpers.route_enricher.NavRepository")
@patch("common.helpers.route_enricher.FixRepository")
def test_enrich_dct_segment_calls_get_point_and_returns_one_enriched(
    mock_fix_repo: MagicMock,
    mock_nav_repo: MagicMock,
) -> None:
    """DCT segment is enriched via get_point and yields one EnrichedRouteSegment."""
    point = _make_point(50.5, 14.5)
    mock_fix_repo.get_closest_fix.return_value = point
    flight_pos = _make_flight_position(50.0, 14.0)
    segments = [_make_raw_segment("DENUT", via_airway="DCT")]
    plan = _make_parsed_plan(segments)

    enricher = RouteEnricher()
    result = enricher.enrich(flight_pos, plan)

    mock_fix_repo.get_closest_fix.assert_called_once_with(50.0, 14.0, "DENUT")
    mock_nav_repo.get_closest_nav_or_fail.assert_not_called()
    assert len(result.segments) == 1
    assert result.segments[0].ident == "DENUT"
    assert result.segments[0].waypoint.lat == 50.5
    assert result.segments[0].waypoint.lon == 14.5

@patch("common.helpers.route_enricher.NavRepository")
@patch("common.helpers.route_enricher.FixRepository")
def test_enrich_segment_with_tas_fl_updates_current_for_next_segment(
    mock_fix_repo: MagicMock,
    mock_nav_repo: MagicMock,
) -> None:
    """Segment with TAS/FL updates current TAS/FL for following segments."""
    mock_fix_repo.get_closest_fix.side_effect = [
        _make_point(50.1, 14.1),
        _make_point(50.2, 14.2),
    ]
    flight_pos = _make_flight_position(ground_speed_kt=400, flight_level=350)
    segments = [
        _make_raw_segment("A", via_airway=None, true_air_speed=320, flight_level=370),
        _make_raw_segment("B", via_airway=None),
    ]
    plan = _make_parsed_plan(segments)

    enricher = RouteEnricher()
    result = enricher.enrich(flight_pos, plan)

    assert result.segments[0].true_air_speed == 320
    assert result.segments[0].flight_level == 370
    assert result.segments[1].true_air_speed == 320
    assert result.segments[1].flight_level == 370

@patch("common.helpers.route_enricher.FixRepository")
@patch("common.helpers.route_enricher.AirwayRepository")
def test_enrich_airway_segment_appends_airway_waypoints(
    mock_airway_repo: MagicMock,
    mock_fix_repo: MagicMock,
) -> None:
    """Segment with via_airway uses get_airway_waypoints and appends enriched segments."""
    seg_ab = _make_airway_mock("A", "B", 50.0, 14.0)
    mock_airway_repo.get_airway_segments.return_value = [seg_ab]
    mock_fix_repo.get_closest_fix.side_effect = [
        _make_point(50.0, 14.0),
        _make_point(51.0, 15.0),
        _make_point(51.0, 15.0),
    ]
    flight_pos = _make_flight_position()
    segments = [
        _make_raw_segment("A", via_airway="L610"),
        _make_raw_segment("B", via_airway=None),
    ]
    plan = _make_parsed_plan(segments)

    enricher = RouteEnricher()
    result = enricher.enrich(flight_pos, plan)

    mock_airway_repo.get_airway_segments.assert_called_once_with("L610")
    assert len(result.segments) >= 2
    assert result.segments[0].ident == "A"
    assert result.segments[1].ident == "B"

def test_enrich_airway_without_next_segment_raises() -> None:
    """When last segment has via_airway and no next segment, ValueError is raised."""
    flight_pos = _make_flight_position()
    segments = [_make_raw_segment("A", via_airway="L610")]
    plan = _make_parsed_plan(segments)

    enricher = RouteEnricher()
    with pytest.raises(ValueError, match="Next segment after A doesn't exist but it should"):
        enricher.enrich(flight_pos, plan)

# ---- get_point ----

@patch("common.helpers.route_enricher.NavRepository")
@patch("common.helpers.route_enricher.FixRepository")
def test_get_point_returns_fix_when_found(
    mock_fix_repo: MagicMock,
    mock_nav_repo: MagicMock,
) -> None:
    """get_point returns Fix when get_closest_fix returns a point."""
    fix = _make_point(50.2, 14.2)
    mock_fix_repo.get_closest_fix.return_value = fix

    enricher = RouteEnricher()
    result = enricher.get_point(50.0, 14.0, "BALTU")

    assert result is fix
    mock_nav_repo.get_closest_nav_or_fail.assert_not_called()

@patch("common.helpers.route_enricher.NavRepository")
@patch("common.helpers.route_enricher.FixRepository")
def test_get_point_returns_nav_when_fix_is_none(
    mock_fix_repo: MagicMock,
    mock_nav_repo: MagicMock,
) -> None:
    """get_point returns Nav when get_closest_fix is None and Nav is found."""
    mock_fix_repo.get_closest_fix.return_value = None
    nav = _make_point(50.3, 14.3)
    mock_nav_repo.get_closest_nav_or_fail.return_value = nav

    enricher = RouteEnricher()
    result = enricher.get_point(50.0, 14.0, "NAV1")

    assert result is nav
    mock_nav_repo.get_closest_nav_or_fail.assert_called_once_with(50.0, 14.0, "NAV1")

@patch("common.helpers.route_enricher.NavRepository")
@patch("common.helpers.route_enricher.FixRepository")
def test_get_point_raises_when_neither_fix_nor_nav_found(
    mock_fix_repo: MagicMock,
    mock_nav_repo: MagicMock,
) -> None:
    """get_point propagates ValueError when NavRepository.get_closest_nav_or_fail raises."""
    mock_fix_repo.get_closest_fix.return_value = None
    mock_nav_repo.get_closest_nav_or_fail.side_effect = ValueError("No NAV point found")

    enricher = RouteEnricher()
    with pytest.raises(ValueError, match="No NAV point found"):
        enricher.get_point(50.0, 14.0, "MISSING")

# ---- get_airway_waypoints ----

@patch("common.helpers.route_enricher.FixRepository")
@patch("common.helpers.route_enricher.AirwayRepository")
def test_get_airway_waypoints_no_segments_for_start_raises(
    mock_airway_repo: MagicMock,
    mock_fix_repo: MagicMock,
) -> None:
    """When no segment contains start_waypoint, ValueError is raised."""
    mock_airway_repo.get_airway_segments.return_value = [
        _make_airway_mock("X", "Y"),
    ]

    enricher = RouteEnricher()
    with pytest.raises(ValueError, match="No segments found for A in airway L610"):
        enricher.get_airway_waypoints("L610", "A", "B", 450, 350)

@patch("common.helpers.route_enricher.FixRepository")
@patch("common.helpers.route_enricher.AirwayRepository")
def test_get_airway_waypoints_one_segment_direct_path(
    mock_airway_repo: MagicMock,
    mock_fix_repo: MagicMock,
) -> None:
    """Single segment A-B returns enriched segments for A and B."""
    seg = _make_airway_mock("A", "B", 50.0, 14.0)
    mock_airway_repo.get_airway_segments.return_value = [seg]
    mock_fix_repo.get_closest_fix.side_effect = [
        _make_point(50.0, 14.0),
        _make_point(51.0, 15.0),
    ]

    enricher = RouteEnricher()
    result = enricher.get_airway_waypoints("L610", "A", "B", 450, 350)

    assert len(result) == 2
    assert result[0].ident == "A"
    assert result[0].waypoint.lat == 50.0
    assert result[1].ident == "B"
    assert result[1].waypoint.lat == 51.0
    assert result[0].true_air_speed == 450
    assert result[0].flight_level == 350

@patch("common.helpers.route_enricher.FixRepository")
@patch("common.helpers.route_enricher.AirwayRepository")
def test_get_airway_waypoints_one_segment_no_route_to_end_raises(
    mock_airway_repo: MagicMock,
    mock_fix_repo: MagicMock,
) -> None:
    """Single start segment that does not lead to end_waypoint raises (waypoint not found)."""
    seg = _make_airway_mock("A", "B", 50.0, 14.0)
    mock_airway_repo.get_airway_segments.return_value = [seg]

    enricher = RouteEnricher()
    with pytest.raises(ValueError, match="Waypoint B not found in airway L610"):
        enricher.get_airway_waypoints("L610", "A", "Z", 450, 350)

    mock_fix_repo.get_closest_fix.assert_not_called()

@patch("common.helpers.route_enricher.FixRepository")
@patch("common.helpers.route_enricher.AirwayRepository")
def test_get_airway_waypoints_two_segments_first_path_used(
    mock_airway_repo: MagicMock,
    mock_fix_repo: MagicMock,
) -> None:
    """Two segments from start_waypoint: first path leading to end is used."""
    seg1 = _make_airway_mock("A", "B", 50.0, 14.0)
    seg2 = _make_airway_mock("A", "C", 50.0, 14.0)
    mock_airway_repo.get_airway_segments.return_value = [seg1, seg2]
    mock_fix_repo.get_closest_fix.side_effect = [
        _make_point(50.0, 14.0),
        _make_point(51.0, 15.0),
    ]

    enricher = RouteEnricher()
    result = enricher.get_airway_waypoints("L610", "A", "B", 450, 350)

    assert len(result) == 2
    assert result[0].ident == "A"
    assert result[1].ident == "B"

@patch("common.helpers.route_enricher.FixRepository")
@patch("common.helpers.route_enricher.AirwayRepository")
def test_get_airway_waypoints_two_segments_second_path_used(
    mock_airway_repo: MagicMock,
    mock_fix_repo: MagicMock,
) -> None:
    """Two segments from start_waypoint: second segment leads A-B; order matters (B path)."""
    seg1 = _make_airway_mock("A", "B", 50.0, 14.0)
    seg2 = _make_airway_mock("A", "X", 50.0, 14.0)
    mock_airway_repo.get_airway_segments.return_value = [seg1, seg2]
    mock_fix_repo.get_closest_fix.side_effect = [
        _make_point(50.0, 14.0),
        _make_point(51.0, 15.0),
    ]

    enricher = RouteEnricher()
    result = enricher.get_airway_waypoints("L610", "A", "B", 450, 350)

    assert len(result) == 2
    assert result[0].ident == "A"
    assert result[1].ident == "B"

@patch("common.helpers.route_enricher.AirwayRepository")
def test_get_airway_waypoints_two_segments_neither_reaches_end_raises(
    mock_airway_repo: MagicMock,
) -> None:
    """Two segments but neither path leads to end_waypoint raises (waypoint not found)."""
    seg1 = _make_airway_mock("A", "X", 50.0, 14.0)
    seg2 = _make_airway_mock("A", "Y", 50.0, 14.0)
    mock_airway_repo.get_airway_segments.return_value = [seg1, seg2]

    enricher = RouteEnricher()
    with pytest.raises(ValueError, match="Waypoint .* not found in airway L610"):
        enricher.get_airway_waypoints("L610", "A", "Z", 450, 350)

@patch("common.helpers.route_enricher.AirwayRepository")
def test_get_airway_waypoints_more_than_two_start_segments_raises(
    mock_airway_repo: MagicMock,
) -> None:
    """More than two segments containing start_waypoint raises."""
    seg1 = _make_airway_mock("A", "B", 50.0, 14.0)
    seg2 = _make_airway_mock("A", "C", 50.0, 14.0)
    seg3 = _make_airway_mock("A", "D", 50.0, 14.0)
    mock_airway_repo.get_airway_segments.return_value = [seg1, seg2, seg3]

    enricher = RouteEnricher()
    with pytest.raises(
        ValueError,
        match="More than two segments found for A in airway L610",
    ):
        enricher.get_airway_waypoints("L610", "A", "B", 450, 350)

# ---- _get_points_to_end_waypoint ----

def test_get_points_to_end_waypoint_direct_path() -> None:
    """Single segment from start to end returns [start_waypoint, end_waypoint]."""
    seg = _make_airway_mock("A", "B")
    enricher = RouteEnricher()
    result = enricher._get_points_to_end_waypoint(seg, [seg], "A", "B")
    assert result == ["A", "B"]

def test_get_points_to_end_waypoint_chain_three_segments() -> None:
    """Chain A-B, B-C, C-D from A to D returns [A, B, C, D]."""
    seg_ab = _make_airway_mock("A", "B")
    seg_bc = _make_airway_mock("B", "C")
    seg_cd = _make_airway_mock("C", "D")
    segments = [seg_ab, seg_bc, seg_cd]
    enricher = RouteEnricher()
    result = enricher._get_points_to_end_waypoint(seg_ab, segments, "A", "D")
    assert result == ["A", "B", "C", "D"]

def test_get_points_to_end_waypoint_waypoint_not_found_raises() -> None:
    """When no next segment from current waypoint exists, ValueError is raised."""
    seg_ab = _make_airway_mock("A", "B")
    seg_bc = _make_airway_mock("B", "C")
    segments = [seg_ab, seg_bc]
    enricher = RouteEnricher()
    with pytest.raises(
        ValueError,
        match="Waypoint C not found in airway L610",
    ):
        enricher._get_points_to_end_waypoint(seg_ab, segments, "A", "Z")


def test_get_points_to_end_waypoint_more_than_one_next_segment_raises() -> None:
    """When two segments leave the same waypoint, ValueError is raised."""
    seg_ab = _make_airway_mock("A", "B")
    seg_bd = _make_airway_mock("B", "D")
    seg_be = _make_airway_mock("B", "E")
    segments = [seg_ab, seg_bd, seg_be]
    enricher = RouteEnricher()
    with pytest.raises(
        ValueError,
        match="More results than expected for airway with point B",
    ):
        enricher._get_points_to_end_waypoint(seg_ab, segments, "A", "D")

# ---- _convert_identifiers_into_enriched_segments ----

@patch("common.helpers.route_enricher.NavRepository")
@patch("common.helpers.route_enricher.FixRepository")
def test_convert_identifiers_into_enriched_segments_calls_get_point_per_ident(
    mock_fix_repo: MagicMock,
    mock_nav_repo: MagicMock,
) -> None:
    """_convert_identifiers_into_enriched_segments calls get_point for each ident."""
    mock_fix_repo.get_closest_fix.side_effect = [
        _make_point(50.0, 14.0),
        _make_point(50.5, 14.5),
        _make_point(51.0, 15.0),
    ]
    enricher = RouteEnricher()
    result = enricher._convert_identifiers_into_enriched_segments(
        ["A", "B", "C"], 50.0, 14.0, 450, 350
    )
    assert len(result) == 3
    assert result[0].ident == "A"
    assert result[0].waypoint.lat == 50.0
    assert result[0].true_air_speed == 450
    assert result[0].flight_level == 350
    assert result[1].ident == "B"
    assert result[2].ident == "C"
    assert mock_fix_repo.get_closest_fix.call_count == 3
