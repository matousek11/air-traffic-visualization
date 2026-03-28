"""Replay speed change request payload."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ReplaySpeedRequest(BaseModel):
    """Request body to step replay speed up or down by one unit."""

    increase: bool = Field(
        description=(
            "True to increase replay speed by 1 unit, "
            "false to decrease by 1 unit (not below 1)."
        ),
    )
