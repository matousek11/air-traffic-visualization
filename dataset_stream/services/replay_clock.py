"""Tick clock for mapping dataset times into replay ticks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class ReplayClockState:
    """In-memory clock state for the replay worker."""
    dataset_min_time: datetime
    dataset_max_time: datetime
    current_tick_sim_time: datetime
    speed: float
    tick_interval_seconds: float


class ReplayClock:
    """Tick clock for mapping dataset time to replay ticks (in-memory)."""

    def __init__(
        self,
        *,
        dataset_min_time: datetime,
        dataset_max_time: datetime,
        speed: float,
        tick_interval_seconds: float,
    ) -> None:
        """Initialize the replay clock."""
        self._state = ReplayClockState(
            dataset_min_time=dataset_min_time,
            dataset_max_time=dataset_max_time,
            current_tick_sim_time=dataset_min_time,
            speed=speed,
            tick_interval_seconds=tick_interval_seconds,
        )

    @property
    def state(self) -> ReplayClockState:
        """Return the current clock state snapshot."""
        return self._state

    def set_speed(self, speed: float) -> None:
        """Update replay speed for future tick advancement.

        Args:
            speed: Speed multiplier (>1).
        """
        if speed < 1:
            return
        self._state.speed = speed

    def advance_one_tick(self) -> None:
        """Advance the current sim time by one tick."""
        increment_seconds = (
            self._state.tick_interval_seconds * self._state.speed
        )
        self._state.current_tick_sim_time = (
            self._state.current_tick_sim_time
            + timedelta(seconds=increment_seconds)
        )

    def is_past_end(self) -> bool:
        """Return True when the current tick sim time is beyond a dataset end."""
        return self._state.current_tick_sim_time > self._state.dataset_max_time

    def clamp_tick_time_for_final_snapshot(self) -> datetime:
        """Return tick_time for the last snapshot (clamped to dataset_max_time)."""
        if self.is_past_end():
            return self._state.dataset_max_time
        return self._state.current_tick_sim_time

    @property
    def progress_percent(self) -> float:
        """Compute progress percentage based on the current tick sim time."""
        total = (
            self._state.dataset_max_time - self._state.dataset_min_time
        ).total_seconds()
        if total <= 0:
            return 100.0
            
        current = (
            self.clamp_tick_time_for_final_snapshot()
            - self._state.dataset_min_time
        ).total_seconds()
        percent = 100.0 * current / total
        return max(0.0, min(percent, 100.0))
