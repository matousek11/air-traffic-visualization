"""
Houses flight object with its methods
"""

from pydantic import BaseModel

class Flight(BaseModel):
    """
    Represents flight object
    """
    flight_id: str
    plane_type: str
    lat: float
    lon: float
    heading: int
    flight_level: int
    speed: int

    def get_creation_string(self) -> str:
        """Return string with which new flight in BlueSky can be created"""
        return (
            f"CRE {self.flight_id} {self.plane_type} {self.lat} {self.lon} "
            f"{self.heading} FL{self.flight_level} {self.speed}"
        )
