"""
Represents points of plane in time and geographic coordinate system
"""

class Position:
    """
    Represents points of plane in time and geographic coordinate system
    """
    def __init__(
            self,
            timestamp: int,
            lon: float,
            lat: float,
            flight_level: float
    ):
        self.timestamp = timestamp
        self.lon = lon
        self.lat = lat
        self.flight_level = flight_level
