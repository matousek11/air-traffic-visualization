"""
Tests for RouteTreeTransformer (flight plan AST to ParsedFlightPlan).
"""
from typing import Any, List, Tuple

import lark
import pytest

from models.flight_parser.arrival_procedure import ArrivalProcedure
from models.flight_parser.departure_procedure import DepartureProcedure
from models.flight_parser.initial_route_config import InitialRouteConfig
from models.flight_parser.parsed_flight_plan import ParsedFlightPlan
from models.flight_parser.raw_route_segment import RawRouteSegment
from services.route_parser import RouteParser
from services.route_tree_transformer import RouteTreeTransformer


# ---- change ----

def test_change_invalid_format_returns_none_dict() -> None:
    """Tests: invalid SPEED_LEVEL format returns both Nones, no exception."""
    t = RouteTreeTransformer()
    result = t.change(["X123F456"])
    assert result["true_air_speed"] is None
    assert result["flight_level"] is None


def test_change_n0459f340_ktas_and_fl() -> None:
    """Tests: N0459F340 gives true_air_speed 459, flight_level 340."""
    t = RouteTreeTransformer()
    result = t.change(["N0459F340"])
    assert result["true_air_speed"] == 459
    assert result["flight_level"] == 340


def test_change_m078f350_mach_to_ktas() -> None:
    """Tests: M078F350 gives Mach 0.78*580 KTAS, flight_level 350."""
    t = RouteTreeTransformer()
    result = t.change(["M078F350"])
    assert result["true_air_speed"] == 452  # 0.78 * 580
    assert result["flight_level"] == 350


def test_change_k_unit_kmh_to_knots() -> None:
    """Tests: K unit (km/h) is converted to knots."""
    t = RouteTreeTransformer()
    result = t.change(["K0500F100"])
    expected_ktas = int(500 * 0.539957)
    assert result["true_air_speed"] == expected_ktas
    assert result["flight_level"] == 100


def test_change_altitude_s_metric() -> None:
    """Tests: S altitude unit (metric) is converted to flight level."""
    t = RouteTreeTransformer()
    result = t.change(["N0450S1110"])
    assert result["true_air_speed"] == 450
    assert result["flight_level"] == int(round(1110 * 0.328084, 0))


# ---- waypoint_node ----

def test_waypoint_node_ident_only() -> None:
    """Tests: waypoint with ident only has no speed/level."""
    t = RouteTreeTransformer()
    result = t.waypoint_node(["BALTU"])
    assert result["ident"] == "BALTU"
    assert result["true_air_speed"] is None
    assert result["flight_level"] is None


def test_waypoint_node_with_change() -> None:
    """Tests: waypoint with change dict merges speed and level."""
    t = RouteTreeTransformer()
    change_dict = {"true_air_speed": 400, "flight_level": 350}
    result = t.waypoint_node(["LAM", change_dict])
    assert result["ident"] == "LAM"
    assert result["true_air_speed"] == 400
    assert result["flight_level"] == 350


# ---- leg ----

def test_leg_without_connection() -> None:
    """Tests: leg with no connection has via_airway None."""
    t = RouteTreeTransformer()
    node_data = {"ident": "DENUT", "true_air_speed": None, "flight_level": None}
    seg = t.leg([node_data, None])
    assert isinstance(seg, RawRouteSegment)
    assert seg.ident == "DENUT"
    assert seg.via_airway is None


def test_leg_with_connection() -> None:
    """Tests: leg with connection sets via_airway."""
    t = RouteTreeTransformer()
    node_data = {"ident": "BALTU", "true_air_speed": None, "flight_level": None}
    seg = t.leg([node_data, "L610"])
    assert seg.ident == "BALTU"
    assert seg.via_airway == "L610"


# ---- connection and DCT ----

def test_connection_dct() -> None:
    """Tests: connection with DCT returns 'DCT'."""
    t = RouteTreeTransformer()
    assert t.connection(["DCT"]) == "DCT"


def test_connection_airway() -> None:
    """Tests: connection with airway returns airway id."""
    t = RouteTreeTransformer()
    assert t.connection(["L610"]) == "L610"


def test_dct_returns_dct() -> None:
    """Tests: DCT terminal returns 'DCT'."""
    t = RouteTreeTransformer()
    assert t.DCT(["DCT"]) == "DCT"


# ---- initial_config ----

def test_initial_config_returns_initial_route_config() -> None:
    """Tests: initial_config returns InitialRouteConfig with parsed values."""
    t = RouteTreeTransformer()
    result = t.initial_config(["N0450F310"])
    assert isinstance(result, InitialRouteConfig)
    assert result.raw == "N0450F310"
    assert result.true_air_speed == 450
    assert result.flight_level == 310


# ---- departure_proc and destination_proc ----

def test_departure_proc_none() -> None:
    """Tests: departure_proc with None returns None."""
    t = RouteTreeTransformer()
    assert t.departure_proc([None]) is None


def test_departure_proc_ident() -> None:
    """Tests: departure_proc with ident returns DepartureProcedure."""
    t = RouteTreeTransformer()
    result = t.departure_proc(["OKL1A"])
    assert isinstance(result, DepartureProcedure)
    assert result.ident == "OKL1A"


def test_destination_proc_none() -> None:
    """Tests: destination_proc with None returns None."""
    t = RouteTreeTransformer()
    assert t.destination_proc([None]) is None


def test_destination_proc_ident() -> None:
    """Tests: destination_proc with ident returns ArrivalProcedure."""
    t = RouteTreeTransformer()
    result = t.destination_proc(["BALTU1K"])
    assert isinstance(result, ArrivalProcedure)
    assert result.ident == "BALTU1K"


# ---- route ----

def test_route_single_segment_no_config_no_procs() -> None:
    """Tests: route with one segment, no config or procedures."""
    t = RouteTreeTransformer()
    seg = RawRouteSegment(ident="DENUT", via_airway=None)
    items: List[Tuple[int, Any]] = [(0, seg)]
    result = t.route(items)
    assert isinstance(result, ParsedFlightPlan)
    assert result.config is None
    assert len(result.segments) == 1
    assert result.segments[0].ident == "DENUT"
    assert result.departure_procedure is None
    assert result.arrival_procedure is None


def test_route_with_config_and_procedures() -> None:
    """Tests: route with config, segment, departure and arrival."""
    t = RouteTreeTransformer()
    config = InitialRouteConfig(
        raw="N0450F310", true_air_speed=450, flight_level=310
    )
    seg = RawRouteSegment(ident="LAM", via_airway="L610")
    dep = DepartureProcedure(ident="OKL1A")
    arr = ArrivalProcedure(ident="BALTU1K")
    items = [(0, config), (1, dep), (2, seg), (3, arr)]
    result = t.route(items)
    assert result.config is config
    assert len(result.segments) == 1
    assert result.segments[0].ident == "LAM"
    assert result.departure_procedure == dep
    assert result.arrival_procedure == arr


# ---- RouteParser.parse (full route) ----

def test_parser_parse_minimal_route() -> None:
    """Tests: parse minimal route returns ParsedFlightPlan with 2 segments."""
    parser = RouteParser()
    result = parser.parse("DENUT DCT LAM")
    assert isinstance(result, ParsedFlightPlan)
    assert result.config is None
    assert result.departure_procedure is None
    assert result.arrival_procedure is None
    assert len(result.segments) == 2
    assert result.segments[0].ident == "DENUT"
    assert result.segments[0].via_airway == "DCT"
    assert result.segments[1].ident == "LAM"
    assert result.segments[1].via_airway is None


def test_parser_parse_with_initial_config() -> None:
    """Tests: parse with initial config sets config and segments."""
    parser = RouteParser()
    result = parser.parse("N0450F310 DENUT L610 LAM")
    assert result.config is not None
    assert result.config.true_air_speed == 450
    assert result.config.flight_level == 310
    assert len(result.segments) >= 2
    assert result.segments[0].ident == "DENUT"
    assert result.segments[0].via_airway == "L610"


def test_parser_parse_with_sid_star() -> None:
    """Tests: parse with SID/STAR sets departure and arrival procedure."""
    parser = RouteParser()
    result = parser.parse("OKL1A DENUT L610 LAM BALTU1K")
    assert hasattr(result.departure_procedure, "ident")
    assert result.departure_procedure.ident == "OKL1A"
    assert hasattr(result.arrival_procedure, "ident")
    assert result.arrival_procedure.ident == "BALTU1K"
    assert len(result.segments) >= 2


def test_parser_parse_invalid_raises() -> None:
    """Tests: invalid route string raises Lark exception."""
    parser = RouteParser()
    with pytest.raises(lark.UnexpectedInput):
        parser.parse("???")
