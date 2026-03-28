"""Replay controller and background worker for dataset replay."""

from __future__ import annotations

import threading
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.engine import Engine

from dataset_stream.enums import ReplayState
from dataset_stream.response_models.replay_status_response import (
    ReplayStatusResponse,
)
from dataset_stream.services.replay_clock import ReplayClock
from dataset_stream.services.replay_db_writer import ReplayDbWriter
from dataset_stream.services.replay_snapshot_selector import (
    ReplaySnapshotSelector,
)

class ReplayController:
    """Controller for running dataset replay as a background worker."""

    def __init__(
        self,
        *,
        engine: Engine,
        dataset_table_name: str,
        default_speed: float = 1.0,
        default_tick_interval_seconds: float = 5.0,
    ) -> None:
        """Initialize replay controller.

        Args:
            engine: SQLAlchemy engine for reading dataset and writing.
            dataset_table_name: Source table name with denormalized samples.
            default_speed: Default replay speed multiplier.
            default_tick_interval_seconds: Tick interval
        """
        self._engine = engine
        self._dataset_table_name = dataset_table_name
        self._default_speed = default_speed
        self._default_tick_interval_seconds = default_tick_interval_seconds

        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        # Used for update loop control
        self._stop_event = threading.Event()
        self._running = False
        self._stopped_reason: str | None = None

        self._clock: ReplayClock | None = None
        self._prev_active_flights: set[str] = set()

        self._snapshot_selector = ReplaySnapshotSelector(
            dataset_table_name=dataset_table_name,
        )
        self._db_writer = ReplayDbWriter()

    def start(
        self,
        *,
        speed: float,
        tick_interval_seconds: float,
    ) -> ReplayStatusResponse:
        """Start replay worker.

        Args:
            speed: Speed multiplier (>=1).
            tick_interval_seconds: Wall-clock tick interval.

        Returns:
            Current status after starting.

        Raises:
            ValueError: When replay is already running or invalid args.
        """
        if speed < 1:
            raise ValueError("speed must be >= 1")
        if tick_interval_seconds <= 0:
            raise ValueError("tick_interval_seconds must be > 0")

        with self._lock:
            if self._running:
                raise ValueError("replay already running")

            dataset_min_time, dataset_max_time = self._load_dataset_bounds()
            if dataset_min_time is None or dataset_max_time is None:
                raise ValueError("dataset is empty")

            self._clock = ReplayClock(
                dataset_min_time=dataset_min_time,
                dataset_max_time=dataset_max_time,
                speed=speed,
                tick_interval_seconds=tick_interval_seconds,
            )
            self._prev_active_flights = set()
            self._stopped_reason = None

            self._stop_event.clear()
            self._running = True

            self._thread = threading.Thread(
                target=self._run_loop,
                daemon=True,
            )
            self._thread.start()

            return self.status()

    def stop(self) -> ReplayStatusResponse:
        """Stop replay worker."""
        with self._lock:
            if not self._running:
                return self.status()

            self._running = False
            self._stopped_reason = "stopped_by_user"
            self._stop_event.set()

            self._thread.join(timeout=10.0)

        return self.status()

    def adjust_speed(self, increase: bool) -> ReplayStatusResponse:
        """Increase or decrease replay speed by 1 unit (minimum 1).

        Args:
            increase: True to add 1 to speed, False to subtract 1 when above 1.

        Returns:
            Current status after applying the change.

        Raises:
            ValueError: When replay has not been started.
        """
        with self._lock:
            if self._clock is None:
                raise ValueError("replay not started")
            current = self._clock.state.speed
            if increase:
                new_speed = current + 1.0
            else:
                new_speed = current - 1.0

            new_speed = max(1.0, new_speed)
            self._clock.set_speed(new_speed)
        return self.status()

    def status(self) -> ReplayStatusResponse:
        """Return the current replay status."""
        with self._lock:
            if self._clock is None:
                return ReplayStatusResponse(
                    running=False,
                    speed=self._default_speed,
                    tick_interval_seconds=self._default_tick_interval_seconds,
                    dataset_min_time=None,
                    dataset_max_time=None,
                    current_tick_sim_time=None,
                    progress_percent=0.0,
                    stopped_reason=self._stopped_reason,
                    state=ReplayState.NOT_STARTED,
                )

            state = (
                ReplayState.RUNNING if self._running else ReplayState.STOPPED
            )
            clock = self._clock.state
            return ReplayStatusResponse(
                running=self._running,
                speed=clock.speed,
                tick_interval_seconds=clock.tick_interval_seconds,
                dataset_min_time=clock.dataset_min_time,
                dataset_max_time=clock.dataset_max_time,
                current_tick_sim_time=(
                    self._clock.clamp_tick_time_for_final_snapshot()
                ),
                progress_percent=self._clock.progress_percent,
                stopped_reason=self._stopped_reason,
                state=state,
            )

    def reset(self) -> ReplayStatusResponse:
        """Stop replay and reset application DB tables."""
        self.stop()
        with self._lock:
            self._clock = None
            self._prev_active_flights = set()
            self._stopped_reason = None
        return self.status()

    def _load_dataset_bounds(self) -> tuple[datetime | None, datetime | None]:
        """Load dataset min/max sample_time from dataset_flight_positions."""
        query = text(
            f"""
            SELECT
                MIN(sample_time) AS min_ts,
                MAX(sample_time) AS max_ts
            FROM {self._dataset_table_name}
            """,
        )
        with self._engine.connect() as conn:
            row = conn.execute(query).mappings().first()
        if row is None:
            return None, None

        return row["min_ts"], row["max_ts"]

    def _run_loop(self) -> None:
        """Main worker loop."""
        while not self._stop_event.is_set():
            with self._lock:
                if not self._running or self._clock is None:
                    return
                tick_time = self._clock.state.current_tick_sim_time
                dataset_max_time = self._clock.state.dataset_max_time
                tick_interval_seconds = self._clock.state.tick_interval_seconds

            if tick_time > dataset_max_time:
                # Final snapshot: clamp to dataset_max_time and stop.
                final_tick_time = dataset_max_time
                with self._lock:
                    if self._clock is not None:
                        self._clock.state.current_tick_sim_time = (
                            final_tick_time
                        )
                    self._stopped_reason = "dataset_finished"
                    self._running = False

                self._send_tick(final_tick_time)
                self._stop_event.set()
                return

            self._send_tick(tick_time)

            # Wait wall-clock tick duration, speed changes during this sleep
            # should apply to the next tick (next_tick_sim_time).
            if self._stop_event.wait(tick_interval_seconds):
                return

            with self._lock:
                if self._clock is None:
                    return
                self._clock.advance_one_tick()

    def _send_tick(self, tick_time_utc: datetime) -> None:
        """Select a snapshot and write it to application DB."""
        # Atomic DB transaction for the tick.
        with self._engine.begin() as conn:
            selection = self._snapshot_selector.select_latest_snapshot_rows(
                conn=conn,
                tick_time_utc=tick_time_utc,
                window_seconds=self._default_tick_interval_seconds,
            )
            current_active = self._db_writer.apply_snapshot(
                conn=conn,
                snapshot_rows=selection.rows,
                prev_active_flights=self._prev_active_flights,
            )

        with self._lock:
            self._prev_active_flights = current_active

