"""
Houses flight object for BlueSky simulation
"""

from pydantic import BaseModel

class Flight(BaseModel):
    """
    Represents flight object for BlueSky simulation
    """
    flight_id: str
    plane_type: str
    lat: float
    lon: float
    heading: int
    flight_level: int
    target_flight_level: int | None = None
    speed: int
    vertical_speed: float

    def get_creation_string(self) -> str:
        """Return string with which new flight in BlueSky can be created"""
        return (
            f"CRE {self.flight_id} {self.plane_type} {self.lat} {self.lon} "
            f"{self.heading} FL{self.flight_level} {self.speed}"
        )

    def get_vertical_speed(self) -> str:
        if self.vertical_speed == 0 or self.target_flight_level is None:
            return f"{self.flight_id} VNAV ON"

        return f"ALT {self.flight_id} {self.target_flight_level * 100} {self.vertical_speed}"
