"""Snapshot data selector for dataset replay."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.engine import Connection

from dataset_stream.services.replay_types import DatasetSnapshotRow


@dataclass(frozen=True)
class SnapshotSelectionResult:
    """Result of selecting the latest snapshots for all flights."""
    rows: list[DatasetSnapshotRow]
    active_flights_current: set[str]


class ReplaySnapshotSelector:
    """Select the per-flight latest snapshot from the dataset table for the current tick."""

    def __init__(self, *, dataset_table_name: str) -> None:
        """Create a snapshot selector."""
        self._dataset_table_name = dataset_table_name

    def select_latest_snapshot_rows(
        self,
        *,
        conn: Connection,
        tick_time_utc: datetime,
        window_seconds: float,
    ) -> SnapshotSelectionResult:
        """Select the latest per-flight rows within a window.

        Args:
            conn: SQLAlchemy connection.
            tick_time_utc: Current tick time in UTC.
            window_seconds: Window size in seconds (e.g., 5.0).

        Returns:
            Snapshots with selected rows and active flights.
        """
        window_start = tick_time_utc - timedelta(seconds=window_seconds)

        query = text(
            f"""
            SELECT DISTINCT ON (flight_id)
                flight_id,
                sample_time,
                time_over,
                aircraft_type,
                origin,
                destination,
                lat,
                lon,
                flight_level,
                route_string,
                ground_speed_kt,
                track_heading,
                vertical_rate_fpm,
                heading
            FROM {self._dataset_table_name}
            WHERE sample_time <= :tick_time
                AND sample_time > :window_start
            ORDER BY flight_id, sample_time DESC
            """,
        )

        result = conn.execute(
            query,
            {
                "tick_time": tick_time_utc,
                "window_start": window_start,
            },
        )

        mappings = result.mappings().all()
        rows: list[DatasetSnapshotRow] = []
        current_active_flights: set[str] = set()
        for m in mappings:
            flight_id = str(m["flight_id"])
            current_active_flights.add(flight_id)
            rows.append(
                DatasetSnapshotRow(
                    flight_id=flight_id,
                    sample_time=m["sample_time"],
                    time_over=m["time_over"],
                    aircraft_type=m["aircraft_type"],
                    origin=m["origin"],
                    destination=m["destination"],
                    lat=float(m["lat"]),
                    lon=float(m["lon"]),
                    flight_level=m["flight_level"],
                    route_string=m["route_string"],
                    ground_speed_kt=m["ground_speed_kt"],
                    track_heading=m["track_heading"],
                    vertical_rate_fpm=m["vertical_rate_fpm"],
                    heading=m["heading"],
                ),
            )

        return SnapshotSelectionResult(
            rows=rows,
            active_flights_current=current_active_flights,
        )

