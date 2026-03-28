"""Replay lifecycle state"""

from __future__ import annotations

from enum import StrEnum


class ReplayState(StrEnum):
    """Lifecycle state of dataset replay."""
    RUNNING = "running"
    STOPPED = "stopped"
    NOT_STARTED = "not_started"
