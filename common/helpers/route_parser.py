"""Lark-based parser for ICAO Item 15 route strings."""

import re

from lark import Lark

from common.models.flight_parser.parsed_flight_plan import ParsedFlightPlan
from common.helpers.route_tree_transformer import RouteTreeTransformer

# Same shapes as SPEED_LEVEL in the grammar (single token).
_SPEED_LEVEL_TOKEN = re.compile(
    r"^(?:N|K)\d{4}(?:F|A|S|M)\d{3,4}$|^M\d{3}(?:F|A|S|M)\d{3,4}$",
)


def preprocess_route_string(route: str) -> str:
    """
    Drop reserved DCT when the lexer would treat it as the first waypoint.

    Removes leading DCT token(s), and DCT immediately after an initial
    SPEED_LEVEL token (e.g., N0447F380 DCT AMULU).

    Args:
        route: Raw Item 15 style route string.

    Returns:
        Normalized string for parsing.
    """
    parts = route.strip().split()
    while parts and parts[0].upper() == "DCT":
        parts.pop(0)
    while (
        len(parts) >= 2
        and _SPEED_LEVEL_TOKEN.match(parts[0])
        and parts[1].upper() == "DCT"
    ):
        parts.pop(1)
    return " ".join(parts)


class RouteParser:
    """Build a Lark parser and transform trees to ParsedFlightPlan."""

    def __init__(self) -> None:
        self.grammar = r"""
                    ?start: route

                    route: [initial_config] departure_proc? (leg)+ destination_proc?
                    
                    # Leg: point and route that goes out of point
                    leg: waypoint_node (connection)?
                    
                    waypoint_node: (IDENTIFIER | COORDINATE) [change]
                    
                    change: "/" SPEED_LEVEL
                    
                    departure_proc: PROCEDURE
                    destination_proc: PROCEDURE
                    
                    connection: DCT | AIRWAY_UPPER | AIRWAY
                    
                    # terminals (Item 15: ATS route designators — ICAO Doc 4444 / PANS-ATM)
                    DCT: "DCT"
                    # Exclude reserved DCT (direct), it must only match connection, not waypoint
                    IDENTIFIER: /(?!DCT$)[A-Z0-9]{2,5}/        # BALTU, OKL, 10N
                    COORDINATE: /\d{2,4}[NS]\d{3,5}[EW]/ # 52N020E, 5230N02030E
                    # Upper ATS routes (U + letter + digits), e.g. UN133, UL863; lex before IDENTIFIER
                    AIRWAY_UPPER.2: /U[A-Z][0-9]{1,4}/
                    AIRWAY: /[A-Z][0-9]{1,4}[A-Z]?/    # L610, M872, Z93
                    PROCEDURE: /[A-Z][A-Z0-9]{1,4}[1-9][A-HJ-NP-Z]/ | /[A-Z][A-Z0-9]{1,4}[1-9][0-9]/ # OKL1A (SID), BALTU1K (STAR)
                    SPEED_LEVEL: /(N|K)\d{4}(F|A|S|M)\d{3,4}/ | /M\d{3}(F|A|S|M)\d{3,4}/  # N0459F340, M078F350
                    initial_config: SPEED_LEVEL
                    
                    %import common.WS
                    %ignore WS
                """
        self.parser = Lark(self.grammar, start="route")
        self.transformer = RouteTreeTransformer()

    def parse(self, route: str) -> ParsedFlightPlan:
        """
        Parse flight plan into flight plan object

        :param route: planned route for flight in string format (DENUT L610 LAM)
        """
        tree = self.parser.parse(preprocess_route_string(route))
        return self.transformer.transform(tree)
