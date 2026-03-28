"""Domain types for dataset replay."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DatasetSnapshotRow:
    """A single snapshot row selected from the NM B2B dataset."""
    flight_id: str
    sample_time: datetime
    time_over: datetime

    aircraft_type: str | None
    origin: str | None
    destination: str | None

    lat: float
    lon: float
    flight_level: int | None

    route_string: str | None

    ground_speed_kt: int | None = None
    track_heading: int | None = None
    vertical_rate_fpm: int | None = None
    heading: int | None = None
