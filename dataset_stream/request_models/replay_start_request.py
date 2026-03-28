"""Replay start request payload."""

from __future__ import annotations

from pydantic import BaseModel


class ReplayStartRequest(BaseModel):
    """Request payload to start dataset replay."""
    speed: float = 1.0
    tick_interval_seconds: float = 5.0
