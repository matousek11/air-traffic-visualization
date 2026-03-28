"""Import NM B2B flight position CSV into a Timescale hypertable."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.engine import Engine

from common.helpers.logging_service import LoggingService
from dataset_stream.import_script.csv_io import load_filtered_rows
from dataset_stream.import_script.derived_kinematics import apply_pairwise_kinematics
from dataset_stream.import_script.schema import drop_and_create_hypertable
from dataset_stream.services.replay_types import DatasetSnapshotRow

logger = LoggingService.get_logger(__name__)


@dataclass(frozen=True)
class ImportResult:
    """Summary counts after a CSV import run."""
    rows_imported: int
    rows_skipped: int


def _insert_rows(
    conn: Connection,
    table_name: str,
    rows: list[DatasetSnapshotRow],
) -> None:
    """Insert all rows using parameterized statements.

    Args:
        conn: Active SQLAlchemy connection.
        table_name: Target table name.
        rows: Rows to insert.
    """
    statement = text(
        f"""
        INSERT INTO {table_name} (
            sample_time,
            time_over,
            flight_id,
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
        ) VALUES (
            :sample_time,
            :time_over,
            :flight_id,
            :aircraft_type,
            :origin,
            :destination,
            :lat,
            :lon,
            :flight_level,
            :route_string,
            :ground_speed_kt,
            :track_heading,
            :vertical_rate_fpm,
            :heading
        )
        """,
    )
    for row in rows: # TODO: could be optimized for batch saving
        conn.execute(
            statement,
            {
                "sample_time": row.sample_time,
                "time_over": row.time_over,
                "flight_id": row.flight_id,
                "aircraft_type": row.aircraft_type,
                "origin": row.origin,
                "destination": row.destination,
                "lat": row.lat,
                "lon": row.lon,
                "flight_level": row.flight_level,
                "route_string": row.route_string,
                "ground_speed_kt": row.ground_speed_kt,
                "track_heading": row.track_heading,
                "vertical_rate_fpm": row.vertical_rate_fpm,
                "heading": row.heading,
            },
        )


def import_flight_positions_csv(
    *,
    csv_path: Path,
    table_name: str,
    engine: Engine,
) -> ImportResult:
    """
    Load CSV, recreate the hypertable,
    and insert all accepted rows with calculated kinematic values.

    Args:
        csv_path: Path to the flight positions CSV file.
        table_name: Target table name.
        engine: SQLAlchemy engine

    Returns:
        Counts of imported and skipped rows.

    Raises:
        ValueError: When the CSV header is wrong.
        FileNotFoundError: When csv_path does not exist.
    """
    rows, skipped = load_filtered_rows(csv_path)
    with engine.begin() as conn:
        drop_and_create_hypertable(conn, table_name)
        _insert_rows(conn, table_name, rows)
        apply_pairwise_kinematics(conn, table_name)
    logger.info(
        "Import finished: %s rows into %s (skipped %s)",
        len(rows),
        table_name,
        skipped,
    )
    return ImportResult(rows_imported=len(rows), rows_skipped=skipped)
