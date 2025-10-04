"""Houses flight plan waypoint DTO"""

from pydantic import BaseModel

class Waypoint(BaseModel):
    """Represents waypoint on flight's flight plan"""
    name: str
    flight_level: int
    speed: int
