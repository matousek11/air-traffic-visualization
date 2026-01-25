"""Pydantic model for MTCD event API response."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class MTCDEventResponse(BaseModel):
    """Represents MTCD event for API response."""

    id: int = Field(description="MTCD event ID")
    flight_id_1: str = Field(description="First flight ID involved in the conflict")
    flight_id_2: str = Field(description="Second flight ID involved in the conflict")
    detected_at: datetime = Field(description="Timestamp when the conflict was detected")
    middle_point_lat: Optional[float] = Field(
        description="Latitude of center of closest approach point"
    )
    middle_point_lon: Optional[float] = Field(
        description="Longitude of center of closest approach point"
    )
    horizontal_distance: Optional[float] = Field(
        description="Horizontal distance at closest approach in nautical miles"
    )
    vertical_distance: Optional[float] = Field(
        description="Vertical distance at closest approach in nautical miles"
    )
    remaining_time: Optional[float] = Field(
        description="Time remaining until closest approach in hours"
    )
    active: bool = Field(description="Whether the conflict is still active")
    last_checked: Optional[datetime] = Field(
        description="Timestamp when the conflict was last checked"
    )

    class Config:
        """Pydantic config."""

        from_attributes = True
