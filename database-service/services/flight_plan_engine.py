from models.flight_parser.enriched_flight_plan import EnrichedFlightPlan
from repositories.flight_position_repository import FlightPositionRepository
from services.route_enricher import RouteEnricher
from services.route_parser import RouteParser


class FlightPlanEngine:
    """
    Handle parsing of string flight plan to EnrichedFlightPlan
    """
    def __init__(self):
        self.parser = RouteParser()
        self.enricher = RouteEnricher()

    def process_flight_plan(self, flight_id: str, raw_string: str) -> EnrichedFlightPlan:
        """
        Handle parsing of string flight plan to EnrichedFlightPlan

        :param flight_id: ID of the flight like CSA201
        :param raw_string: String flight plan like "DENUT L610 LAM"
        """
        # 1. Parse string
        raw_parsed_flightplan = self.parser.parse(raw_string)

        # get flight details
        flight_position = FlightPositionRepository.get_latest_position(flight_id)

        # 2. Enrich flight plan with Data
        return self.enricher.enrich(flight_position, raw_parsed_flightplan)