"""
Houses detail flight with flight plan and wind class
"""

from .flight import Flight
from .waypoint import Waypoint
from .wind import Wind

class FlightDetail(Flight):
    """
    Extends Flight object with flight plan and wind
    """
    flight_plan: list[Waypoint]
    wind: Wind
