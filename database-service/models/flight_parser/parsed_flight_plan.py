from dataclasses import dataclass
from typing import List, Optional

from models.flight_parser.initial_route_config import InitialRouteConfig
from models.flight_parser.raw_route_segment import RawRouteSegment

@dataclass
class ParsedFlightPlan:
    """Container for whole route parser result"""
    config: Optional[InitialRouteConfig]
    segments: List[RawRouteSegment]
    departure_procedure: str
    arrival_procedure: str