"""Place for wind DTO for BlueSky simulation API response"""
from pydantic import BaseModel


class Wind(BaseModel):
    """
    Used as response model for wind API endpoint

    :param heading: Direction from which is wind incoming in degrees
    :param speed: Wind speed in kts
    :param lat: Latitude of wind definition point
    :param lon: Longitude of wind definition point
    :param altitude: Altitude in feet
    """
    heading: float
    speed: float
    lat: float
    lon: float
    altitude: int