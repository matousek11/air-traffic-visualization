"""DB writer for applying replay snapshots into application tables."""

from __future__ import annotations

from collections.abc import Iterable

from psycopg2.extras import Json
from sqlalchemy import text
from sqlalchemy.engine import Connection

from dataset_stream.services.replay_types import DatasetSnapshotRow


class ReplayDbWriter:
    """Write one replay tick snapshot into application DB tables."""

    def apply_snapshot(
        self,
        *,
        conn: Connection,
        snapshot_rows: list[DatasetSnapshotRow],
        prev_active_flights: set[str],
    ) -> set[str]:
        """Apply a snapshot: upsert positions, update flight activity.

        Args:
            conn: SQLAlchemy connection (inside a transaction).
            snapshot_rows: Latest snapshot rows for current tick.
            prev_active_flights: Active flights from previous tick.

        Returns:
            Set of currently active flight ids.
        """
        curr_active_flights = {row.flight_id for row in snapshot_rows}

        self._upsert_flights(conn, snapshot_rows)
        self._upsert_flight_positions(conn, snapshot_rows)

        missing = prev_active_flights - curr_active_flights
        if missing:
            self._deactivate_missing_flights(conn, missing)
            self._archive_stale_mtcd_events(conn, missing)

        return curr_active_flights

    @staticmethod
    def _upsert_flights(
        conn: Connection,
        snapshot_rows: Iterable[DatasetSnapshotRow],
    ) -> None:
        """Upsert flight metadata and set active=true."""
        for row in snapshot_rows:
            statement = text(
                """
                INSERT INTO flight (
                    flight_id,
                    aircraft_type,
                    origin,
                    destination,
                    active
                ) VALUES (
                    :flight_id,
                    :aircraft_type,
                    :origin,
                    :destination,
                    true
                )
                ON CONFLICT (flight_id) DO UPDATE SET
                    aircraft_type = EXCLUDED.aircraft_type,
                    origin = EXCLUDED.origin,
                    destination = EXCLUDED.destination,
                    active = true
                """,
            )
            conn.execute(
                statement,
                {
                    "flight_id": row.flight_id,
                    "aircraft_type": row.aircraft_type,
                    "origin": row.origin,
                    "destination": row.destination,
                },
            )

    @staticmethod
    def _upsert_flight_positions(
        conn: Connection,
        snapshot_rows: Iterable[DatasetSnapshotRow],
    ) -> None:
        """Upsert flight_position for snapshot rows."""
        statement = text(
            """
            INSERT INTO flight_position (
                flight_id,
                ts,
                lat,
                lon,
                flight_level,
                ground_speed_kt,
                heading,
                track_heading,
                vertical_rate_fpm,
                sector_id,
                route,
                flight_plan_json,
                geom
            ) VALUES (
                :flight_id,
                :ts,
                :lat,
                :lon,
                :flight_level,
                :ground_speed_kt,
                :heading,
                :track_heading,
                :vertical_rate_fpm,
                :sector_id,
                :route,
                :flight_plan_json,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
            )
            ON CONFLICT (flight_id, ts) DO UPDATE SET
                lat = EXCLUDED.lat,
                lon = EXCLUDED.lon,
                flight_level = EXCLUDED.flight_level,
                ground_speed_kt = EXCLUDED.ground_speed_kt,
                heading = EXCLUDED.heading,
                track_heading = EXCLUDED.track_heading,
                vertical_rate_fpm = EXCLUDED.vertical_rate_fpm,
                sector_id = EXCLUDED.sector_id,
                route = EXCLUDED.route,
                flight_plan_json = EXCLUDED.flight_plan_json,
                geom = EXCLUDED.geom
            """,
        )
        for row in snapshot_rows:
            conn.execute(
                statement,
                {
                    "flight_id": row.flight_id,
                    "ts": row.time_over,
                    "lat": row.lat,
                    "lon": row.lon,
                    "flight_level": row.flight_level,
                    "ground_speed_kt": row.ground_speed_kt,
                    "heading": row.heading,
                    "track_heading": row.track_heading,
                    "vertical_rate_fpm": row.vertical_rate_fpm,
                    "sector_id": None,
                    "route": row.route_string,
                    "flight_plan_json": (
                        Json(row.flight_plan_json)
                        if row.flight_plan_json is not None
                        else None
                    ),
                },
            )

    @staticmethod
    def _deactivate_missing_flights(
        conn: Connection,
        missing: set[str],
    ) -> None:
        """Set flight.active=false for missing flights."""
        statement = text(
            """
            UPDATE flight
            SET active = false
            WHERE flight_id = ANY(CAST(:missing AS text[]))
            """,
        )
        conn.execute(statement, {"missing": list(missing)})

    @staticmethod
    def _archive_stale_mtcd_events(
        conn: Connection,
        missing: set[str],
    ) -> None:
        """Archive MTCD events involving missing flights."""
        stmt = text(
            """
            UPDATE mtcd_event
            SET active = false, last_checked = now()
            WHERE active = true
              AND (
                flight_id_1 = ANY(CAST(:missing AS text[]))
                OR flight_id_2 = ANY(CAST(:missing AS text[]))
              )
            """,
        )
        conn.execute(stmt, {"missing": list(missing)})

