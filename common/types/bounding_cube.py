from typing import NamedTuple


class BoundingCube(NamedTuple):
    """Represents bounding cube used for simple check of collision paths"""
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float
    min_flight_level: int
    max_flight_level: int