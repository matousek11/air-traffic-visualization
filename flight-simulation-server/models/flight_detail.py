"""
Houses detail flight with flight plan and wind class
"""

from .flight import Flight
from .waypoint import Waypoint
from .wind import Wind

class FlightDetail(Flight):
    """
    Extends a Flight object with flight plan and wind
    """
    flight_plan: list[Waypoint]
    route_string: str | None = None
    wind: Wind
