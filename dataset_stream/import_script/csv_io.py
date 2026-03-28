"""Load and validate flight position rows from NM B2B-style CSV files."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path

from common.helpers.logging_service import LoggingService
from dataset_stream.services.replay_types import DatasetSnapshotRow

logger = LoggingService.get_logger(__name__)

EXPECTED_HEADER = (
    "sample_time",
    "time_over",
    "flight_id",
    "aircraft_type",
    "origin",
    "destination",
    "lat",
    "lon",
    "flight_level",
    "route_string",
)


def parse_iso_datetime_utc(value: str) -> datetime:
    """Parse an ISO 8601 timestamp string into an aware UTC datetime.

    Args:
        value: ISO string.

    Returns:
        Timezone-aware datetime in UTC.

    Raises:
        ValueError: When the string cannot be parsed.
    """
    parsed = datetime.fromisoformat(value.strip())
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _parse_optional_iso_datetime_utc(raw: str | None) -> datetime | None:
    """Parse ISO timestamp or return None if the cell is blank.

    Args:
        raw: CSV cell text, or None.

    Returns:
        Aware UTC datetime, or None when empty/whitespace.

    Raises:
        ValueError: When the cell is non-empty but not a valid ISO datetime.
    """
    text_val = str(raw or "").strip()
    if text_val == "":
        return None
    return parse_iso_datetime_utc(text_val)


def _blank_to_none(value: str) -> str | None:
    """Return None for empty or whitespace-only strings."""
    stripped = value.strip()
    if stripped == "":
        return None
    return stripped


def _parse_optional_float(raw: str | None) -> float | None:
    """Parse a float from CSV text, or None if blank.

    Args:
        raw: CSV cell text, or None.

    Returns:
        Parsed float, or None when empty/whitespace.

    Raises:
        ValueError: When the cell is non-empty but not a valid float.
    """
    text_val = str(raw or "").strip()
    if text_val == "":
        return None
    return float(text_val)


def _parse_optional_int(raw: str | None) -> int | None:
    """Parse an integer flight level from CSV text, or None if blank.

    Args:
        raw: CSV cell text, or None.

    Returns:
        Parsed integer, or None when empty/whitespace.

    Raises:
        ValueError: When the cell is non-empty but not a valid number.
    """
    text_val = str(raw or "").strip()
    if text_val == "":
        return None
    return int(float(text_val))


def load_filtered_rows(
    csv_path: Path,
) -> tuple[list[DatasetSnapshotRow], int]:
    """Read CSV rows and keep rows with the required time and flight identity.

    Args:
        csv_path: Path to the CSV file.

    Returns:
        Tuple of (accepted rows, number of skipped rows).

    Raises:
        ValueError: When the header row does not match the expected columns.
        FileNotFoundError: When csv_path does not exist.
    """
    rows: list[DatasetSnapshotRow] = []
    skipped = 0

    with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("CSV has no header row")
        header = tuple(reader.fieldnames)
        if header != EXPECTED_HEADER:
            msg = (
                f"Unexpected CSV header {header!r}; "
                f"expected {EXPECTED_HEADER!r}"
            )
            raise ValueError(msg)

        for raw in reader:
            try:
                sample_time = _parse_optional_iso_datetime_utc(
                    raw.get("sample_time"),
                )
                time_over = _parse_optional_iso_datetime_utc(
                    raw.get("time_over"),
                )
                lat = _parse_optional_float(raw.get("lat"))
                lon = _parse_optional_float(raw.get("lon"))
                flight_level = _parse_optional_int(raw.get("flight_level"))
            except (ValueError, KeyError) as exc:
                logger.warning("Skipping malformed row: %s", exc)
                skipped += 1
                continue

            if sample_time is None or time_over is None:
                skipped += 1
                continue

            flight_id_val = _blank_to_none(raw.get("flight_id", "") or "")
            if flight_id_val is None:
                skipped += 1
                continue

            ac = _blank_to_none(raw.get("aircraft_type", "") or "")
            orig = _blank_to_none(raw.get("origin", "") or "")
            dest = _blank_to_none(raw.get("destination", "") or "")
            route = _blank_to_none(raw.get("route_string", "") or "")
            rows.append(
                DatasetSnapshotRow(
                    sample_time=sample_time,
                    time_over=time_over,
                    flight_id=flight_id_val,
                    aircraft_type=ac,
                    origin=orig,
                    destination=dest,
                    lat=lat,
                    lon=lon,
                    flight_level=flight_level,
                    route_string=route,
                ),
            )

    logger.info(
        "Loaded %s rows, skipped %s rows from %s",
        len(rows),
        skipped,
        csv_path,
    )
    return rows, skipped
