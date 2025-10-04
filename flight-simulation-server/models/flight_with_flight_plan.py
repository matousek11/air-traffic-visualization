"""
Houses Flight with flight plan class
"""

from .flight import Flight
from .waypoint import Waypoint

class FlightWithFlightPlan(Flight):
    """
    Extends Flight object with flight plan
    """
    flight_plan: list[Waypoint]
