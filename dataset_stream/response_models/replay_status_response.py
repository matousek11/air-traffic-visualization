"""Replay status response model."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from dataset_stream.enums.replay_state import ReplayState


class ReplayStatusResponse(BaseModel):
    """Response payload for replay controller status."""
    running: bool
    speed: float
    tick_interval_seconds: float

    dataset_min_time: datetime | None = None
    dataset_max_time: datetime | None = None
    current_tick_sim_time: datetime | None = None

    progress_percent: float
    stopped_reason: str | None = None

    state: ReplayState

