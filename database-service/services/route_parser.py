from lark import Lark

from models.flight_parser.parsed_flight_plan import ParsedFlightPlan
from services.route_tree_transformer import RouteTreeTransformer


class RouteParser:
    def __init__(self) -> None:
        self.grammar = """
                    ?start: route

                    route: [initial_config] departure_proc? (leg)+ destination_proc?
                    
                    # Leg: point and route that goes out of point
                    leg: waypoint_node (connection)?
                    
                    waypoint_node: (IDENTIFIER | COORDINATE) [change]
                    
                    change: "/" SPEED_LEVEL
                    
                    departure_proc: PROCEDURE
                    destination_proc: PROCEDURE
                    
                    connection: DCT | AIRWAY
                    
                    # terminals
                    DCT: "DCT"
                    IDENTIFIER: /[A-Z0-9]{2,5}/        # BALTU, OKL, 10N
                    COORDINATE: /\d{2,4}[NS]\d{3,5}[EW]/ # 52N020E, 5230N02030E
                    AIRWAY: /[A-Z][0-9]{1,4}[A-Z]?/    # L610, Z93
                    PROCEDURE: /[A-Z]{2,5}[0-9][A-Z]/ # OKL1A (SID), BALTU1K (STAR)
                    SPEED_LEVEL: /(N|K)\d{4}(F|A|S|M)\d{3,4}/ | /M\d{3}(F|A|S|M)\d{3,4}/  # N0459F340, M078F350
                    initial_config: SPEED_LEVEL
                    
                    %import common.WS
                    %ignore WS
                """
        self.parser = Lark(self.grammar, start='route')
        self.transformer = RouteTreeTransformer()

    def parse(self, route: str) -> ParsedFlightPlan:
        """
        Parse flight plan into flight plan object

        :param route: planned route for flight in string format (DENUT L610 LAM)
        """
        tree = self.parser.parse(route)
        return self.transformer.transform(tree)