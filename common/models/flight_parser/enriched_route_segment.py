from dataclasses import dataclass

from common.models.flight_parser.waypoint import Waypoint


@dataclass
class EnrichedRouteSegment:
    ident: str  # (BALTU) or coordinates
    waypoint: Waypoint
    true_air_speed: int | None
    flight_level: int | None
    # hours
    time_to_segment_entry: float = 0

    def __repr__(self):
        extras = ""
        if self.true_air_speed: extras += f" [{self.true_air_speed}/{self.flight_level}]"
        return f"({self.ident} lat: {self.waypoint.lat} lon: {self.waypoint.lon} speed: {self.true_air_speed} flight_level: {self.flight_level} time_to_segment_entry: {self.time_to_segment_entry} -->{extras})"