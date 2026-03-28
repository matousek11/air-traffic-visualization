"""Tests for dataset_stream CSV loading and filtering."""

from __future__ import annotations

import csv
from datetime import timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from dataset_stream import ImportResult
from dataset_stream import import_flight_positions_csv
from dataset_stream.import_script.csv_io import EXPECTED_HEADER
from dataset_stream.import_script.csv_io import (
    load_filtered_rows,
    parse_iso_datetime_utc,
)
from dataset_stream.services.replay_types import DatasetSnapshotRow


def test_parse_iso_datetime_utc_z_suffix() -> None:
    """Z suffix parses to aware UTC."""
    result = parse_iso_datetime_utc("2026-03-21T16:04:03Z")
    assert result.tzinfo == timezone.utc
    assert result.year == 2026
    assert result.month == 3
    assert result.day == 21
    assert result.hour == 16
    assert result.minute == 4
    assert result.second == 3


def test_load_filtered_rows_keeps_complete_rows() -> None:
    """Rows with all required fields are loaded."""
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "sample.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(EXPECTED_HEADER))
            writer.writeheader()
            writer.writerow(
                {
                    "sample_time": "2026-03-21T16:04:03Z",
                    "time_over": "2026-03-21T16:02:14Z",
                    "flight_id": "PO00102964",
                    "aircraft_type": "S22T",
                    "origin": "LKLT",
                    "destination": "LKTB",
                    "lat": "49.305",
                    "lon": "16.093",
                    "flight_level": "68",
                    "route_string": "N0181F090 BEKVI",
                },
            )
        rows, skipped = load_filtered_rows(path)
        assert skipped == 0
        assert len(rows) == 1
        row = rows[0]
        assert isinstance(row, DatasetSnapshotRow)
        assert row.flight_id == "PO00102964"
        assert row.flight_level == 68
        assert row.lat == pytest.approx(49.305)
        assert row.route_string == "N0181F090 BEKVI"


def test_load_filtered_rows_skips_missing_time_over() -> None:
    """Rows with empty time_over are skipped."""
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "sample.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(EXPECTED_HEADER))
            writer.writeheader()
            writer.writerow(
                {
                    "sample_time": "2026-03-21T16:04:03Z",
                    "time_over": "",
                    "flight_id": "X",
                    "aircraft_type": "",
                    "origin": "",
                    "destination": "",
                    "lat": "",
                    "lon": "",
                    "flight_level": "",
                    "route_string": "",
                },
            )
            writer.writerow(
                {
                    "sample_time": "2026-03-21T16:04:03Z",
                    "time_over": "2026-03-21T16:02:14Z",
                    "flight_id": "Y",
                    "aircraft_type": "B738",
                    "origin": "EPWA",
                    "destination": "LKPR",
                    "lat": "50.0",
                    "lon": "14.0",
                    "flight_level": "100",
                    "route_string": "DCT",
                },
            )
        rows, skipped = load_filtered_rows(path)
        assert skipped == 1
        assert len(rows) == 1
        assert rows[0].flight_id == "Y"


def test_load_filtered_rows_accepts_null_lat_lon_fl() -> None:
    """Rows may omit lat, lon, flight_level (imported as None)."""
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "sample.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(EXPECTED_HEADER))
            writer.writeheader()
            writer.writerow(
                {
                    "sample_time": "2026-03-21T16:04:03Z",
                    "time_over": "2026-03-21T16:02:14Z",
                    "flight_id": "NULLGEO",
                    "aircraft_type": "",
                    "origin": "",
                    "destination": "",
                    "lat": "",
                    "lon": "",
                    "flight_level": "",
                    "route_string": "",
                },
            )
        rows, skipped = load_filtered_rows(path)
        assert skipped == 0
        assert len(rows) == 1
        row = rows[0]
        assert row.flight_id == "NULLGEO"
        assert row.lat is None
        assert row.lon is None
        assert row.flight_level is None


def test_load_filtered_rows_rejects_bad_header() -> None:
    """Wrong CSV header raises ValueError."""
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "bad.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            handle.write("wrong,header\n")
        with pytest.raises(ValueError, match="Unexpected CSV header"):
            load_filtered_rows(path)


def test_public_api_import_from_dataset_stream() -> None:
    """Top-level dataset_stream package exposes the importer."""
    assert ImportResult(rows_imported=0, rows_skipped=0).rows_imported == 0
    assert callable(import_flight_positions_csv)
