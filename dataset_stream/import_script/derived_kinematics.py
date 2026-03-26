"""Pairwise kinematic columns calculation for denormalized flight positions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import replace
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from common.helpers.physics_calculator import PhysicsCalculator
from common.models.position import Position
from dataset_stream.import_script.csv_io import DenormalizedFlightPositionRow


@dataclass(frozen=True)
class FlightUpdates:
    """Pass 1 SQL bind parameters for kinematics and imputed position."""
    kin_params: list[dict[str, object]]
    position_params: list[dict[str, object]]


def _is_flight_position_complete(row: DenormalizedFlightPositionRow) -> bool:
    """Return True when lat, lon, and flight_level are all set.

    Args:
        row: Flight position row.

    Returns:
        Whether the row has full position and altitude.
    """
    return (
        row.lat is not None
        and row.lon is not None
        and row.flight_level is not None
    )


def _get_time_over_timestamp(row: DenormalizedFlightPositionRow) -> int:
    """Return Unix seconds from time_over.

    Args:
        row: Row with a time_over value set.

    Returns:
        seconds timestamp from time_over.
    """
    return int(row.time_over.timestamp())


def derive_kinematic_data(
    previous: DenormalizedFlightPositionRow,
    current: DenormalizedFlightPositionRow,
    calculator: PhysicsCalculator,
) -> tuple[int, int, int, int] | None:
    """Compute derived kinematics for one segment (previous -> current).

    Args:
        previous: Prior sample of the same flight (ordered by sample_time).
        current: Current sample.
        calculator: PhysicsCalculator instance for heading.

    Returns:
        (ground_speed_kt, track_heading, vertical_rate_fpm, heading) or
        None when flight samples don't have positive time distance or complete flight position data.
    """
    if not _is_flight_position_complete(previous) or not _is_flight_position_complete(current):
        return None

    delta_t = (current.time_over - previous.time_over).total_seconds()
    if delta_t <= 0:
        return None

    prev_pos = Position(
        _get_time_over_timestamp(previous),
        previous.lon,
        previous.lat,
        float(previous.flight_level),
    )
    curr_pos = Position(
        _get_time_over_timestamp(current),
        current.lon,
        current.lat,
        float(current.flight_level),
    )

    kmh = PhysicsCalculator.get_horizontal_speed(curr_pos, prev_pos)
    ground_speed_kt = int(round(PhysicsCalculator.km_to_nm(kmh)))

    track_heading = calculator.calculate_heading(
        previous.lat,
        previous.lon,
        current.lat,
        current.lon,
    )
    track_heading = int(track_heading)

    vertical_m_per_min = PhysicsCalculator.get_vertical_speed(
        curr_pos,
        prev_pos,
    )
    vertical_rate_fpm = int(
        round(PhysicsCalculator.meters_to_feet(vertical_m_per_min)),
    )

    heading = track_heading
    return ground_speed_kt, track_heading, vertical_rate_fpm, heading


def _denormalized_row_from_mapping(
    row: Mapping[str, object],
) -> DenormalizedFlightPositionRow:
    """Build a DenormalizedFlightPositionRow from a DB result mapping.

    Args:
        row: Row mapping with keys matching hypertable column names.

    Returns:
        Frozen row for PhysicsCalculator pairwise use.

    Raises:
        TypeError: When sample_time or time_over are not datetimes.
    """
    sample_time = row["sample_time"]
    time_over = row["time_over"]
    if not isinstance(sample_time, datetime) or not isinstance(
        time_over,
        datetime,
    ):
        msg = "sample_time and time_over must be datetime"
        raise TypeError(msg)
    return DenormalizedFlightPositionRow(
        sample_time=sample_time,
        time_over=time_over,
        flight_id=str(row["flight_id"]),
        aircraft_type=_optional_str(row["aircraft_type"]),
        origin=_optional_str(row["origin"]),
        destination=_optional_str(row["destination"]),
        lat=_optional_float(row["lat"]),
        lon=_optional_float(row["lon"]),
        flight_level=_optional_int(row["flight_level"]),
        route_string=_optional_str(row["route_string"]),
    )


def _locf_position_with_flags(
    rows: list[DenormalizedFlightPositionRow],
) -> tuple[list[DenormalizedFlightPositionRow], list[bool]]:
    """Forward-fill missing lat/lon/fl from the last complete sample per flight.

    Args:
        rows: Samples for one flight, oldest first.

    Returns:
        Tuple of (rows after LOCF transformation, position_imputed flags per row).
    """
    last_complete: tuple[float, float, int] | None = None
    out: list[DenormalizedFlightPositionRow] = []
    flags: list[bool] = []
    for row in rows:
        lat = row.lat
        lon = row.lon
        fl = row.flight_level
        imputed = False
        if last_complete is not None:
            if lat is None:
                lat = last_complete[0]
                imputed = True
            if lon is None:
                lon = last_complete[1]
                imputed = True
            if fl is None:
                fl = last_complete[2]
                imputed = True
        new_row = replace(row, lat=lat, lon=lon, flight_level=fl)
        out.append(new_row)
        flags.append(imputed)
        if lat is not None and lon is not None and fl is not None:
            last_complete = (lat, lon, fl)
    return out, flags


def fill_in_missing_values(
    sorted_flight_rows: list[DenormalizedFlightPositionRow],
    calculator: PhysicsCalculator,
) -> FlightUpdates:
    """Applies LOCF to lat/lon/fl, then computes kinematics.

    Args:
        sorted_flight_rows: All samples for one flight, oldest first.
        calculator: PhysicsCalculator instance.

    Returns:
        Kinematic and position UPDATE parameter lists.
    """
    imputed_rows, is_position_imputed = _locf_position_with_flags(
        sorted_flight_rows,
    )
    position_params: list[dict[str, object]] = []
    # prepare imputed positions for db update
    for index, imputed in enumerate(is_position_imputed):
        if not imputed:
            continue
        new_row = imputed_rows[index]
        position_params.append(
            {
                "flight_id": new_row.flight_id,
                "sample_time": new_row.sample_time,
                "lat": new_row.lat,
                "lon": new_row.lon,
                "flight_level": new_row.flight_level,
            },
        )

    # derive kinematics
    kin_params: list[dict[str, object]] = []
    last_derived: tuple[int, int, int, int] | None = None
    for index in range(1, len(imputed_rows)):
        prev_row = imputed_rows[index - 1]
        curr_row = imputed_rows[index]
        is_curr_imputed = is_position_imputed[index]

        if is_curr_imputed:
            # if imputed, just copy last kinematics values
            if last_derived is None:
                continue
            ground_speed = last_derived[0]  # pylint: disable=unsubscriptable-object
            track_heading = last_derived[1]  # pylint: disable=unsubscriptable-object
            vertical_rate = last_derived[2]  # pylint: disable=unsubscriptable-object
            heading = last_derived[3]  # pylint: disable=unsubscriptable-object
        else:
            # derive data for not imputed position of flight
            derived = derive_kinematic_data(prev_row, curr_row, calculator)
            if derived is not None:
                last_derived = derived
                ground_speed, track_heading, vertical_rate, heading = (
                    derived[0],
                    derived[1],
                    derived[2],
                    derived[3],
                )
            else:
                # if derivation of data not possible put in the latest calculated data
                if last_derived is None:
                    continue
                ground_speed = last_derived[0]  # pylint: disable=unsubscriptable-object
                track_heading = last_derived[1]  # pylint: disable=unsubscriptable-object
                vertical_rate = last_derived[2]  # pylint: disable=unsubscriptable-object
                heading = last_derived[3]  # pylint: disable=unsubscriptable-object
        kin_params.append(
            {
                "ground_speed_kt": ground_speed,
                "track_heading": track_heading,
                "vertical_rate_fpm": vertical_rate,
                "heading": heading,
                "flight_id": curr_row.flight_id,
                "sample_time": curr_row.sample_time,
            },
        )
    return FlightUpdates(
        kin_params=kin_params,
        position_params=position_params,
    )


def apply_pairwise_kinematics(conn: Connection, table_name: str) -> None:
    """Calculates pairwise-derived columns from time_over.

    Args:
        conn: Open SQLAlchemy connection (transaction managed by caller).
        table_name: Hypertable name.
    """
    distinct_flight_ids_sql = text(
        f"""
        SELECT DISTINCT flight_id
        FROM {table_name}
        ORDER BY flight_id
        """,
    )
    get_flight_data_sql = text(
        f"""
        SELECT
            sample_time,
            time_over,
            flight_id,
            aircraft_type,
            origin,
            destination,
            lat,
            lon,
            flight_level,
            route_string
        FROM {table_name}
        WHERE flight_id = :flight_id
        ORDER BY sample_time ASC
        """,
    )
    update_flight_position_sql = text(
        f"""
        UPDATE {table_name}
        SET
            lat = :lat,
            lon = :lon,
            flight_level = :flight_level
        WHERE flight_id = :flight_id AND sample_time = :sample_time
        """,
    )
    update_flight_kinematics_sql = text(
        f"""
        UPDATE {table_name}
        SET
            ground_speed_kt = :ground_speed_kt,
            track_heading = :track_heading,
            vertical_rate_fpm = :vertical_rate_fpm,
            heading = :heading
        WHERE flight_id = :flight_id AND sample_time = :sample_time
        """,
    )

    calculator = PhysicsCalculator()
    flight_id_rows = conn.execute(distinct_flight_ids_sql).fetchall()
    if not flight_id_rows:
        return

    for row in flight_id_rows:
        flight_id = row[0]
        flight_data = conn.execute(
            get_flight_data_sql,
            {"flight_id": flight_id},
        )
        mappings = flight_data.mappings().all()
        flight_rows = [_denormalized_row_from_mapping(m) for m in mappings]
        updates = fill_in_missing_values(flight_rows, calculator)
        for param in updates.position_params:
            conn.execute(update_flight_position_sql, param)
        for param in updates.kin_params:
            conn.execute(update_flight_kinematics_sql, param)


def _optional_str(value: Any) -> str | None:
    """Normalize optional text to str or None.

    Args:
        value: Raw cell value.

    Returns:
        None when value is None, otherwise str(value).
    """
    if value is None:
        return None
    return str(value)


def _optional_float(value: Any) -> float | None:
    """Normalize optional text to float or None.

    Args:
        value: Raw cell value.

    Returns:
        None when value is None, otherwise float(value).
    """
    if value is None:
        return None
    return float(value)


def _optional_int(value: Any) -> int | None:
    """Normalize optional text to int or None.

    Args:
        value: Raw cell value.

    Returns:
        None when value is None, otherwise int(value).
    """
    if value is None:
        return None
    return int(float(value))