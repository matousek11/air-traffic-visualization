"""Lark route tree transformer producing ParsedFlightPlan segments."""

import re

from lark import Transformer

from common.helpers.logging_service import LoggingService
from common.models.flight_parser.arrival_procedure import ArrivalProcedure
from common.models.flight_parser.departure_procedure import DepartureProcedure
from common.models.flight_parser.initial_route_config import InitialRouteConfig
from common.models.flight_parser.parsed_flight_plan import ParsedFlightPlan
from common.models.flight_parser.raw_route_segment import RawRouteSegment

logger = LoggingService.get_logger(__name__)


class RouteTreeTransformer(Transformer):
    """
    Transform Lark AST tree on list of RawSegment objects.
    Methods have same names as rules in grammar
    """

    def route(self, items: list) -> ParsedFlightPlan:
        """
        Represents node rule for route

        :param items: everything parser found (list of (index, item) or flat list)
        :return:
        """
        segments = []
        init_config = None
        departure_procedure = None
        star_procedure = None

        # Normalize: parser passes flat list
        normalized = []
        for index, thing in enumerate(items):
            if isinstance(thing, tuple) and len(thing) == 2:
                normalized.append(thing)
            else:
                normalized.append((index, thing))

        for index, item in normalized:
            if item is None:
                continue
            if isinstance(item, InitialRouteConfig):
                init_config = item
            elif isinstance(item, RawRouteSegment):
                segments.append(item)
            elif isinstance(item, DepartureProcedure):
                departure_procedure = item
            elif isinstance(item, ArrivalProcedure):
                star_procedure = item

        return ParsedFlightPlan(
            config=init_config,
            segments=segments,
            departure_procedure=departure_procedure,
            arrival_procedure=star_procedure
        )

    def initial_config(self, items) -> InitialRouteConfig:
        """Represents terminal rule for initial speed and flight level configuration"""
        # example: "N0450F310"
        change = self.change(items)
        # Parse speed and altitude/flight level
        return InitialRouteConfig(
            raw=items[0],
            true_air_speed=change["true_air_speed"],
            flight_level=change["flight_level"]
        )

    def leg(self, items: list) -> RawRouteSegment:
        """Represents node rule for single leg of route"""
        # rule: leg: waypoint_node (connection)?

        # 1. get result of waypoint_node
        node_data = items[0]

        # 2. Get route if exists
        if len(items) > 1 and items[1] is not None:
            connection = items[1]
        else:
            connection = None

        return RawRouteSegment(
            ident=node_data['ident'],
            via_airway=connection,
            true_air_speed=node_data.get('true_air_speed'),
            flight_level=node_data.get('flight_level')
        )

    def destination_proc(self, items) -> ArrivalProcedure | None:
        """Return arrival procedure name for selected airport"""
        if items[0] is None:
            return None

        return ArrivalProcedure(ident=items[0])

    def departure_proc(self, items) -> DepartureProcedure | None:
        """Return departure procedure name for selected airport"""
        if items[0] is None:
            return None

        return DepartureProcedure(ident=items[0])

    def waypoint_node(self, items) -> dict[str, str | int | None]:
        """Represents single navigation point node rule"""
        # Rule waypoint_node: (IDENTIFIER | COORDINATE) [change]

        # name of point or coordinate (Lark Token)
        ident = str(items[0])

        result = {'ident': ident, 'true_air_speed': None, 'flight_level': None}

        # if exists it is result of rule 'change' (true_air_speed/flight_level)
        if len(items) > 1 and items[1] is not None:
            change_data = items[1]
            result.update(change_data)

        return result

    def change(self, items) -> dict[str, int | None]:
        """
        Takes speed and level change and converts them

        :param items:
        :return: flight_level in feets and speed in true_air_speed in knots
        """
        # rule change: "/" SPEED_LEVEL for example ("N0459F340")
        raw_sl = str(items[0])

        match = re.match(r"([NKM])(\d{3,4})([FASM])(\d{3,4})", raw_sl)
        if not match:
            logger.warning("Unable to parse speed/flight level change: %s", raw_sl)
            return {'true_air_speed': None, 'flight_level': None}

        speed_unit, speed_val, altitude_unit, altitude_val = match.groups()

        # speed unit conversion into ktas
        true_air_speed = None
        if speed_unit == 'N': # KTAS
            true_air_speed = int(speed_val)
        elif speed_unit == 'M': # Mach number
            mach_val = int(speed_val) / 100.0
            # calculated as average speed of sound in FL300
            # instead of current temperature in planned altitude for simplification
            # average speed of mach 1 is defined over here as 580 KTAS
            true_air_speed = int(mach_val * 580)
        elif speed_unit == 'K': # km/h
            true_air_speed = int(int(speed_val) * 0.539957)  # km/h to knots

        if true_air_speed is None:
            raise ValueError(f"Unable to parse and convert air speed: {raw_sl}")

        # conversion to flight levels in feets
        flight_level = None
        if altitude_unit == 'F':
            flight_level = int(altitude_val)
        elif altitude_unit == 'A': # altitude measurement based on mean sea level pressure
            # A045 => 045 * 100 => 4500 feet
            # for sake of simplicity altitude is kept in local altitude
            # as planes near should have same altitude if collision should appear
            flight_level = int(altitude_val)
        elif altitude_unit == 'S': # flight level but in metric system
            # S1110 => FL 11 100 meters
            flight_level = int(round(int(altitude_val) * 0.328084, 0))
        elif altitude_unit == 'M': # altitude measurement in meters based on mean sea level pressure
            # M4500 => 4500 => 4500 meters
            # for sake of simplicity altitude is kept in local altitude
            # as planes near should have same altitude if collision should appear
            flight_level = int(round(int(altitude_val) * 0.0328084, 0))

        if flight_level is None:
            raise ValueError(f"Unable to parse and convert flight level: {raw_sl}")

        return {
            'true_air_speed': true_air_speed,
            'flight_level': flight_level,
        }

    def connection(self, items: list) -> str | None:
        """Airway or DCT between legs."""
        return items[0]

    def DCT(self, items) -> str:
        # Terminal rule for DCT
        return "DCT"
