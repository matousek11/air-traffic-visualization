"""Used as definition for request body"""
from pydantic import BaseModel, Field


class SpeedAction(BaseModel):
    """Used as definition for request body"""
    increase: bool = Field(
        description="True to increase simulation speed by 1 unit, false to decrease by 1 unit"
    )