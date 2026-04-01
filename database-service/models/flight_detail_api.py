"""
Models used for flight API responses.
"""

from pydantic import BaseModel, Field


class Wind(BaseModel):
    """Wind at mentioned position."""
    heading: float = Field(
        ...,
        description="Direction from which wind blows, degrees",
    )
    speed: float = Field(..., description="Wind speed in knots")
    lat: float = Field(..., description="Latitude associated with wind sample")
    lon: float = Field(..., description="Longitude associated with wind sample")
    altitude: int = Field(..., description="Altitude in feet")


class FlightDetailResponse(BaseModel):
    """Flight detail."""
    flight_id: str
    plane_type: str
    lat: float
    lon: float
    heading: int
    flight_level: int
    target_flight_level: int | None = None
    speed: int
    vertical_speed: float
    flight_plan: list[str] = Field(
        default_factory=list,
        description="Waypoint identifiers in route order",
    )
    route_string: str | None = None
    wind: Wind
    track_heading: int
