"""Represents result for closest approach point calculation for API response"""
from pydantic import BaseModel, Field

class ClosestApproachPoint(BaseModel):
    """
    Represents result for closest approach point calculation
    for API response
    """
    first_flight_id: str = Field(
        description="Flight that was used "
                    "for calculation of closest approach point",
    )
    second_flight_id: str = Field(
        description="Flight that was used for "
                    "calculation of closest approach point",
    )
    horizontal_distance: float = Field(
        description="Closest horizontal distance between flights in NM",
    )
    vertical_distance: float = Field(
        description="Closest vertical distance between flights in NM",
    )
    time_to_closest_approach: float = Field(
        description="Time to closest approach in hours",
    )
    middle_point_lat: float = Field(
        description="Latitude of center of closest approach point",
    )
    middle_point_lon: float = Field(
        description="Longitude of center of closest approach point",
    )
    middle_point_fl: float = Field(
        description="Flight level of center of closest approach point",
    )

