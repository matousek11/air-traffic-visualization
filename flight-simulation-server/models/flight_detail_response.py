"""
Houses detail of flight for api response
"""

from .flight_detail import FlightDetail

class FlightDetailResponse(FlightDetail):
    """
    Houses detail of flight for api response
    """
    track_heading: int
