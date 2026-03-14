"""Response models for closest-approach-point endpoint (MTCD pipeline)."""
from pydantic import BaseModel, Field


class ConflictItem(BaseModel):
    """
    Single detected conflict between two flights (one predicted CPA / segment).

    Exposes fields from common.helpers.mtcd_toolkit.Conflict for API response.
    """

    horizontal_distance: float = Field(
        description="Closest horizontal distance between flights in NM",
    )
    vertical_distance: float = Field(
        description="Closest vertical distance between flights in NM",
    )
    time_to_closest_approach: float = Field(
        description="Time to closest approach in hours",
    )
    time_to_conflict_entry: float = Field(
        description="Time to conflict entry in hours",
    )
    time_to_conflict_exit: float = Field(
        description="Time to conflict exit in hours",
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


class ClosestApproachPointsResponse(BaseModel):
    """
    Response for GET /closest-approach-point: flight pair and list of conflicts.

    May contain zero, one, or multiple conflicts for the same pair of flights.
    """

    first_flight_id: str = Field(
        description="First flight ID used for conflict detection",
    )
    second_flight_id: str = Field(
        description="Second flight ID used for conflict detection",
    )
    conflicts: list[ConflictItem] = Field(
        description="List of detected conflicts (predicted CPAs) for this pair",
        default_factory=list,
    )
