"""Compute flight_plan_json for dataset rows during CSV import."""

from __future__ import annotations

from dataclasses import replace

from common.helpers.logging_service import LoggingService
from dataset_stream.services.replay_types import DatasetSnapshotRow
from services.route_plan_expand import expand_route_to_waypoint_names

logger = LoggingService.get_logger(__name__)


def attach_flight_plans_or_skip(
    rows: list[DatasetSnapshotRow],
) -> tuple[list[DatasetSnapshotRow], int]:
    """
    Fill ``flight_plan_json`` from ``route_string`` or drop rows that cannot
    be resolved when a route is present.

    Args:
        rows: Rows loaded from CSV with kinematics not yet applied.

    Returns:
        Rows to insert (with ``flight_plan_json`` set when route was
        non-empty) and an additional skip count for dropped rows.
    """
    cache: dict[str, list[str]] = {}
    out: list[DatasetSnapshotRow] = []
    extra_skipped = 0

    for row in rows:
        route = row.route_string
        if route is None or not str(route).strip():
            out.append(
                replace(row, flight_plan_json=None),
            )
            continue

        cache_key = f"{row.flight_id}\0{route}"
        if cache_key in cache:
            names = cache[cache_key]
            out.append(replace(row, flight_plan_json=names))
            continue

        if row.lat is None or row.lon is None:
            logger.warning(
                "Skipping row with route but missing position: %s",
                row.flight_id,
            )
            extra_skipped += 1
            continue

        names = expand_route_to_waypoint_names(
            route_string=route,
            lat=float(row.lat),
            lon=float(row.lon),
            flight_level=row.flight_level,
            ground_speed_kt=row.ground_speed_kt,
        )
        if names is None:
            logger.warning(
                "Skipping row: could not expand route for %s",
                row.flight_id,
            )
            extra_skipped += 1
            continue

        cache[cache_key] = names
        out.append(replace(row, flight_plan_json=names))

    return out, extra_skipped
