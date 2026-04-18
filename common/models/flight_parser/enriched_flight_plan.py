from dataclasses import dataclass
from typing import List, Optional

from common.models.flight_parser.enriched_route_segment import EnrichedRouteSegment
from common.models.flight_parser.initial_route_config import InitialRouteConfig

@dataclass
class EnrichedFlightPlan:
    """Container for whole route parser result"""
    config: Optional[InitialRouteConfig]
    segments: List[EnrichedRouteSegment]
    departure_procedure: str
    arrival_procedure: str
