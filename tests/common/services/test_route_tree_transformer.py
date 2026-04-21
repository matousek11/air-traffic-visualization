"""
Tests for RouteTreeTransformer (flight plan AST to ParsedFlightPlan).
"""
from typing import Any, List, Tuple

import lark
import pytest

from common.models.flight_parser.arrival_procedure import ArrivalProcedure
from common.models.flight_parser.departure_procedure import DepartureProcedure
from common.models.flight_parser.initial_route_config import InitialRouteConfig
from common.models.flight_parser.parsed_flight_plan import ParsedFlightPlan
from common.models.flight_parser.raw_route_segment import RawRouteSegment
from common.helpers.route_parser import RouteParser, preprocess_route_string
from common.helpers.route_tree_transformer import (
    RouteTreeTransformer,
)


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


def test_parser_upper_ats_route_un133_is_airway_not_waypoint() -> None:
    """Upper ATS designators (ICAO Item 15) lex as airway, not waypoint."""
    parser = RouteParser()
    result = parser.parse("ANTAR UN133 PEREN DCT ABCD")
    assert len(result.segments) == 3
    assert result.segments[0].ident == "ANTAR"
    assert result.segments[0].via_airway == "UN133"
    assert result.segments[1].ident == "PEREN"
    assert result.segments[1].via_airway == "DCT"
    assert result.segments[2].ident == "ABCD"
    assert result.segments[2].via_airway is None


def test_parser_upper_ats_route_ul863_is_airway() -> None:
    """UL863-style upper route matches AIRWAY terminal."""
    parser = RouteParser()
    result = parser.parse("PEREN UL863 EVIVI")
    assert result.segments[0].ident == "PEREN"
    assert result.segments[0].via_airway == "UL863"
    assert result.segments[1].ident == "EVIVI"
    assert result.segments[1].via_airway is None


def test_preprocess_route_string_strips_leading_dct() -> None:
    """Leading DCT tokens are removed, so DCT is not the first waypoint."""
    assert preprocess_route_string("DCT VLM") == "VLM"
    assert preprocess_route_string("  DCT  DCT  AMULU  ") == "AMULU"


def test_preprocess_route_string_strips_dct_after_initial_speed() -> None:
    """DCT after Nxxxx speed/level at the start is not parsed as a waypoint."""
    assert preprocess_route_string("N0447F380 DCT AMULU") == "N0447F380 AMULU"
    assert preprocess_route_string("N0447F380 DCT DCT AMULU") == "N0447F380 AMULU"


def test_parser_dct_not_first_waypoint_after_speed_config() -> None:
    """Full route: first leg after config is AMULU, not DCT."""
    parser = RouteParser()
    result = parser.parse(
        "N0447F380 DCT AMULU DCT KETEL DCT ROGMI T108 LANDU LANDU2A",
    )
    assert result.config is not None
    assert result.segments[0].ident == "AMULU"
    assert result.segments[0].via_airway == "DCT"


# ---- Known parser gaps (xfail) ----
# Each test documents one specific gap identified against the full ICAO 4444 token set.
# Marked strict=True: when a bug is fixed the test must have its xfail removed,
# otherwise it becomes an XPASS → treated as a hard failure by pytest.


# === VFR / mixed IFR-VFR ===

@pytest.mark.xfail(strict=True, reason="VFR speed element (e.g. N0449VFR) not in grammar — SPEED_LEVEL only accepts F/A/S/M altitude codes, not VFR suffix")
def test_parser_rejects_vfr_speed_element() -> None:
    """N0449VFR is a valid ICAO speed+flight-rule element (knots, VFR) that the grammar rejects."""
    parser = RouteParser()
    result = parser.parse("N0449VFR BALTU DCT KOSIT")
    assert result.config is not None


@pytest.mark.xfail(strict=True, reason="VFR and IFR break tokens match IDENTIFIER (3 letters) and become waypoints instead of flight-rule transition markers")
def test_parser_vfr_ifr_break_elements_treated_as_waypoints() -> None:
    """VFR / IFR in the middle of a route should be flight-rule transitions, not waypoints."""
    parser = RouteParser()
    result = parser.parse("BALTU VFR KOSIT IFR DENUT")
    idents = [s.ident for s in result.segments]
    assert "VFR" not in idents
    assert "IFR" not in idents


# === OAT / GAT break elements ===

@pytest.mark.xfail(strict=True, reason="OAT and GAT airspace-type markers not in grammar — both match IDENTIFIER (3 letters) and become waypoints")
def test_parser_oat_gat_break_elements_treated_as_waypoints() -> None:
    """OAT (Operational Air Traffic) and GAT (General Air Traffic) are ICAO break markers, not points."""
    parser = RouteParser()
    result = parser.parse("BALTU OAT KOSIT GAT DENUT")
    idents = [s.ident for s in result.segments]
    assert "OAT" not in idents
    assert "GAT" not in idents


# === IFPSTOP / IFPSTART ===

@pytest.mark.xfail(strict=True, reason="IFPSTOP/IFPSTART are 7-char tokens that exceed IDENTIFIER max of 6, so the parser raises instead of handling them")
def test_parser_rejects_ifpstop_ifpstart() -> None:
    """IFPSTOP / IFPSTART are valid ICAO IFPS delimiters; too long for IDENTIFIER (max 6 chars)."""
    parser = RouteParser()
    result = parser.parse("BALTU IFPSTOP KOSIT IFPSTART DENUT")
    assert result is not None


# === STAY element ===

@pytest.mark.xfail(strict=True, reason="STAY elements (STAY1–STAY9) not in grammar — STAY1 matches IDENTIFIER and becomes a waypoint ident")
def test_parser_stay_element_treated_as_waypoint() -> None:
    """STAY1 is an ICAO holding-pattern indicator; it should not appear as a route waypoint."""
    parser = RouteParser()
    result = parser.parse("BALTU STAY1 KOSIT")
    assert "STAY1" not in [s.ident for s in result.segments]


# === Truncate T ===

@pytest.mark.xfail(strict=True, reason="Truncate element 'T' not in grammar — single-char token cannot match IDENTIFIER (min 2), parse error")
def test_parser_rejects_truncate_t() -> None:
    """'T' signals that the remainder of the route was truncated; currently causes a parse error."""
    parser = RouteParser()
    result = parser.parse("BALTU DCT KOSIT T")
    assert result is not None


# === Cruise Climb C element ===

@pytest.mark.xfail(strict=True, reason="Cruise-climb 'C' indicator not in grammar — 'C' alone is 1 char (below IDENTIFIER min), parse error")
def test_parser_rejects_cruise_climb_c_element() -> None:
    """C/POINT/SPEED-LEVEL-LEVEL is a valid ICAO cruise-climb construct; 'C' is unrecognised."""
    parser = RouteParser()
    result = parser.parse("BALTU DCT KOSIT C/DENUT/N0449F350F400")
    assert result is not None


# === Cruise-climb double altitude ===

@pytest.mark.xfail(strict=True, reason="SPEED_LEVEL regex handles only a single altitude value; N0449F350F400 (two altitudes) does not match and causes parse error")
def test_parser_rejects_cruise_climb_double_altitude() -> None:
    """N0449F350F400 — 'climb from FL350 to FL400 at 449 kt' — is a valid ICAO initial speed/level/level."""
    parser = RouteParser()
    result = parser.parse("N0449F350F400 BALTU DCT KOSIT")
    assert result.config is not None


# === PLUS suffix ===

@pytest.mark.xfail(strict=True, reason="SPEED_LEVEL regex has no PLUS suffix variant; N0449F350PLUS does not match and causes parse error")
def test_parser_rejects_plus_suffix_speed_level() -> None:
    """N0449F350PLUS ('FL350 or above') is a valid ICAO speed/level-plus element."""
    parser = RouteParser()
    result = parser.parse("N0449F350PLUS BALTU DCT KOSIT")
    assert result.config is not None


# === NAT routes ===

@pytest.mark.xfail(strict=True, reason="NAT route designators (NATA, NATB…) not in grammar — NATA matches IDENTIFIER and becomes a waypoint instead of a connection")
def test_parser_nat_route_treated_as_waypoint() -> None:
    """NATA should connect MIMKU to SOSIM; instead it is parsed as a third waypoint."""
    parser = RouteParser()
    result = parser.parse("MIMKU NATA SOSIM")
    assert len(result.segments) == 2
    assert result.segments[0].ident == "MIMKU"
    assert result.segments[0].via_airway == "NATA"
    assert result.segments[1].ident == "SOSIM"


# === PTS routes ===

@pytest.mark.xfail(strict=True, reason="PTS route designators (PTS1, PTSA…) not in grammar — PTS1 matches IDENTIFIER and becomes a waypoint instead of a connection")
def test_parser_pts_route_treated_as_waypoint() -> None:
    """PTS1 should be a route connection between BALTU and KOSIT, not a waypoint."""
    parser = RouteParser()
    result = parser.parse("BALTU PTS1 KOSIT")
    assert len(result.segments) == 2
    assert result.segments[0].ident == "BALTU"
    assert result.segments[0].via_airway == "PTS1"
    assert result.segments[1].ident == "KOSIT"


# === Two-letter prefix airways ===

@pytest.mark.xfail(strict=True, reason="AIRWAY regex /[A-Z][0-9]{1,4}[A-Z]?/ requires exactly one leading letter; LG1 (xx9 pattern) falls through to IDENTIFIER and becomes a waypoint")
def test_parser_two_letter_prefix_airway_treated_as_waypoint() -> None:
    """LG1 is a valid ATS airway (xx9 pattern); it should be a connection, not a waypoint."""
    parser = RouteParser()
    result = parser.parse("BALTU LG1 KOSIT")
    assert len(result.segments) == 2
    assert result.segments[0].ident == "BALTU"
    assert result.segments[0].via_airway == "LG1"
    assert result.segments[1].ident == "KOSIT"


# === SPEED_LEVEL digit-count precision ===

@pytest.mark.xfail(strict=True, reason="SPEED_LEVEL uses \\d{3,4} for altitude — incorrectly accepts N0449F3456 (4 digits after F) which should require exactly 3")
def test_parser_accepts_invalid_fl_four_digits() -> None:
    """N0449F3456 is syntactically wrong (FL must be 3 digits) but the loose \\d{3,4} allows it."""
    parser = RouteParser()
    with pytest.raises(lark.UnexpectedInput):
        parser.parse("N0449F3456 BALTU")


@pytest.mark.xfail(strict=True, reason="SPEED_LEVEL uses \\d{3,4} for altitude — incorrectly accepts N0449S123 (3 digits after S) which should require exactly 4")
def test_parser_accepts_invalid_metric_level_three_digits() -> None:
    """N0449S123 is syntactically wrong (metric level S must be 4 digits) but \\d{3,4} allows 3."""
    parser = RouteParser()
    with pytest.raises(lark.UnexpectedInput):
        parser.parse("N0449S123 BALTU")


# === PBD (Point Bearing Distance) ===

@pytest.mark.xfail(strict=True, reason="PBD regex /[A-Z]{2,3}\\d{6}/ requires minimum 2-letter prefix; single-letter navaid P030029 cannot be parsed")
def test_parser_pbd_single_letter_prefix() -> None:
    """P030029 — navaid 'P' at bearing 030, distance 029 nm — is a valid ICAO significant point."""
    parser = RouteParser()
    result = parser.parse("P030029 DCT BALTU")
    assert result.segments[0].ident == "P030029"


@pytest.mark.xfail(strict=True, reason="PBD regex /[A-Z]{2,3}\\d{6}/ allows max 3-letter prefix; BALTU030029 (5-letter navaid + BD) is split by the lexer into two tokens")
def test_parser_pbd_five_letter_prefix() -> None:
    """BALTU030029 — navaid 'BALTU' at bearing 030, distance 029 nm — should be a single PBD point."""
    parser = RouteParser()
    result = parser.parse("BALTU030029 DCT KOSIT")
    assert result.segments[0].ident == "BALTU030029"


@pytest.mark.xfail(strict=True, reason="COORDINATE+BD not in grammar — 52N020E030029 is split by the lexer: 52N020E becomes COORDINATE, 030029 becomes a separate IDENTIFIER")
def test_parser_coordinate_with_bearing_distance() -> None:
    """52N020E030029 (lat/lon with appended bearing/distance) should resolve to a single waypoint."""
    parser = RouteParser()
    result = parser.parse("52N020E030029 DCT BALTU")
    assert result.segments[0].ident == "52N020E030029"


# === 8-character procedure name ===

@pytest.mark.xfail(strict=True, reason="PROCEDURE regex tops out at 7 chars; BALTU11K ([A-Z]{5}[0-9]{2}[A-Z] = 8 chars) is a valid ICAO STAR that fails to parse")
def test_parser_rejects_eight_char_procedure() -> None:
    """BALTU11K is a valid 8-char STAR (5 letters + 2 digits + 1 letter) unrecognised by the grammar."""
    parser = RouteParser()
    result = parser.parse("DENUT L610 KOSIT BALTU11K")
    assert result.arrival_procedure is not None
    assert result.arrival_procedure.ident == "BALTU11K"


# === Single-letter waypoint ===

@pytest.mark.xfail(strict=True, reason="IDENTIFIER requires min 2 characters; single-letter waypoints valid per ICAO cannot be parsed")
def test_parser_rejects_single_letter_waypoint() -> None:
    """Single-letter waypoint 'N' is syntactically valid per ICAO but fails IDENTIFIER (min 2 chars)."""
    parser = RouteParser()
    result = parser.parse("N DCT BALTU")
    assert result.segments[0].ident == "N"


# === PROCEDURE allows digits in name body ===

@pytest.mark.xfail(strict=True, reason="PROCEDURE regex uses [A-Z0-9] in body — accepts 'B1U1A' which contains a digit mid-name; real SID/STAR names have only letters before the final number+letter")
def test_parser_accepts_procedure_with_digit_in_name_body() -> None:
    """B1U1A has a digit inside the name body — not a valid SID/STAR format, but the regex accepts it."""
    parser = RouteParser()
    with pytest.raises(lark.UnexpectedInput):
        parser.parse("B1U1A DENUT L610 KOSIT")
