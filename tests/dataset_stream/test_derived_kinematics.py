"""Tests for pairwise kinematics helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from common.helpers.physics_calculator import PhysicsCalculator
from dataset_stream.import_script.derived_kinematics import (
    _denormalized_row_from_mapping,
)
from dataset_stream.import_script.derived_kinematics import derive_kinematic_data
from dataset_stream.import_script.derived_kinematics import (
    fill_in_missing_values,
)
from dataset_stream.services.replay_types import DatasetSnapshotRow


def _row(
    *,
    sample_time: datetime,
    time_over: datetime,
    lat: float | None,
    lon: float | None,
    flight_level: int | None,
) -> DatasetSnapshotRow:
    """Build a minimal flight position row for tests.

    Args:
        sample_time: Hypertable time key.
        time_over: Physics segment time.
        lat: Latitude degrees or None.
        lon: Longitude degrees or None.
        flight_level: Flight level or None.

    Returns:
        DatasetSnapshotRow with fixed flight_id and route.
    """
    return DatasetSnapshotRow(
        sample_time=sample_time,
        time_over=time_over,
        flight_id="F1",
        aircraft_type=None,
        origin=None,
        destination=None,
        lat=lat,
        lon=lon,
        flight_level=flight_level,
        route_string=None,
    )


def test_pairwise_update_params_empty_or_single() -> None:
    """No segments when fewer than two samples."""
    calc = PhysicsCalculator()
    empty = fill_in_missing_values([], calc)
    assert not empty.kin_params
    assert not empty.position_params
    t0 = datetime(2026, 3, 21, 16, 0, 0, tzinfo=UTC)
    one = [
        _row(
            sample_time=t0,
            time_over=t0,
            lat=50.0,
            lon=14.0,
            flight_level=100,
        ),
    ]
    single = fill_in_missing_values(one, calc)
    assert not single.kin_params
    assert not single.position_params


def test_pairwise_update_params_two_samples() -> None:
    """Two samples yield one UPDATE dict targeting the second sample_time."""
    calc = PhysicsCalculator()
    t0 = datetime(2026, 3, 21, 16, 0, 0, tzinfo=UTC)
    t1 = datetime(2026, 3, 21, 16, 1, 0, tzinfo=UTC)
    rows = [
        _row(
            sample_time=t0,
            time_over=t0,
            lat=50.0,
            lon=14.0,
            flight_level=100,
        ),
        _row(
            sample_time=t1,
            time_over=t1,
            lat=50.01,
            lon=14.01,
            flight_level=100,
        ),
    ]
    result = fill_in_missing_values(rows, calc)
    assert len(result.kin_params) == 1
    assert not result.position_params
    p0 = result.kin_params[0]
    assert p0["flight_id"] == "F1"
    assert p0["sample_time"] == t1
    assert "ground_speed_kt" in p0
    assert "track_heading" in p0
    assert "vertical_rate_fpm" in p0
    assert "heading" in p0


def test_pairwise_zero_delta_without_prior_derived_skipped() -> None:
    """Equal time_over on the only segment leaves nothing to write (NULL)."""
    calc = PhysicsCalculator()
    t0 = datetime(2026, 3, 21, 16, 0, 0, tzinfo=UTC)
    rows = [
        _row(
            sample_time=t0,
            time_over=t0,
            lat=50.0,
            lon=14.0,
            flight_level=100,
        ),
        _row(
            sample_time=t0 + timedelta(minutes=1),
            time_over=t0,
            lat=50.01,
            lon=14.01,
            flight_level=100,
        ),
    ]
    result = fill_in_missing_values(rows, calc)
    assert not result.kin_params


def test_pairwise_zero_delta_reuses_last_derived() -> None:
    """After a positive-delta segment, zero delta copies last computed ints."""
    calc = PhysicsCalculator()
    t0 = datetime(2026, 3, 21, 16, 0, 0, tzinfo=UTC)
    t1 = datetime(2026, 3, 21, 16, 1, 0, tzinfo=UTC)
    t2 = datetime(2026, 3, 21, 16, 2, 0, tzinfo=UTC)
    rows = [
        _row(
            sample_time=t0,
            time_over=t0,
            lat=50.0,
            lon=14.0,
            flight_level=100,
        ),
        _row(
            sample_time=t1,
            time_over=t1,
            lat=50.01,
            lon=14.01,
            flight_level=100,
        ),
        _row(
            sample_time=t2,
            time_over=t1,
            lat=50.02,
            lon=14.02,
            flight_level=100,
        ),
    ]
    result = fill_in_missing_values(rows, calc)
    assert len(result.kin_params) == 2
    assert result.kin_params[0]["sample_time"] == t1
    assert result.kin_params[1]["sample_time"] == t2
    assert (
        result.kin_params[0]["ground_speed_kt"]
        == result.kin_params[1]["ground_speed_kt"]
    )
    assert (
        result.kin_params[0]["track_heading"]
        == result.kin_params[1]["track_heading"]
    )
    assert (
        result.kin_params[0]["vertical_rate_fpm"]
        == result.kin_params[1]["vertical_rate_fpm"]
    )
    assert result.kin_params[0]["heading"] == result.kin_params[1]["heading"]


def test_pairwise_derived_ints_none_without_geometry() -> None:
    """Incomplete lat/lon/fl yields no derived segment."""
    calc = PhysicsCalculator()
    t0 = datetime(2026, 3, 21, 16, 0, 0, tzinfo=UTC)
    t1 = datetime(2026, 3, 21, 16, 1, 0, tzinfo=UTC)
    prev = _row(
        sample_time=t0,
        time_over=t0,
        lat=50.0,
        lon=14.0,
        flight_level=100,
    )
    curr = _row(
        sample_time=t1,
        time_over=t1,
        lat=None,
        lon=14.01,
        flight_level=100,
    )
    assert derive_kinematic_data(prev, curr, calc) is None


def test_position_imputed_kin_matches_prior_segment() -> None:
    """LOCF-filled row uses last_derived, not a new physics pair."""
    calc = PhysicsCalculator()
    t0 = datetime(2026, 3, 21, 16, 0, 0, tzinfo=UTC)
    t1 = datetime(2026, 3, 21, 16, 1, 0, tzinfo=UTC)
    t2 = datetime(2026, 3, 21, 16, 2, 0, tzinfo=UTC)
    rows = [
        _row(
            sample_time=t0,
            time_over=t0,
            lat=50.0,
            lon=14.0,
            flight_level=100,
        ),
        _row(
            sample_time=t1,
            time_over=t1,
            lat=50.01,
            lon=14.01,
            flight_level=100,
        ),
        _row(
            sample_time=t2,
            time_over=t2,
            lat=None,
            lon=None,
            flight_level=None,
        ),
    ]
    result = fill_in_missing_values(rows, calc)
    assert len(result.position_params) == 1
    assert result.position_params[0]["sample_time"] == t2
    assert len(result.kin_params) == 2
    assert result.kin_params[0]["sample_time"] == t1
    assert result.kin_params[1]["sample_time"] == t2
    assert (
        result.kin_params[0]["ground_speed_kt"]
        == result.kin_params[1]["ground_speed_kt"]
    )


def test_denormalized_row_from_mapping() -> None:
    """DB mapping converts to DenormalizedFlightPositionRow."""
    t0 = datetime(2026, 3, 21, 16, 0, 0, tzinfo=UTC)
    mapping = {
        "sample_time": t0,
        "time_over": t0,
        "flight_id": "X1",
        "aircraft_type": "B738",
        "origin": "LKPR",
        "destination": None,
        "lat": 50.1,
        "lon": 14.2,
        "flight_level": 120,
        "route_string": "DCT",
    }
    row = _denormalized_row_from_mapping(mapping)
    assert row.flight_id == "X1"
    assert row.flight_level == 120
    assert row.destination is None
    assert row.route_string == "DCT"


def test_denormalized_row_from_mapping_nullable_geometry() -> None:
    """Nullable lat/lon/fl from DB map to None."""
    t0 = datetime(2026, 3, 21, 16, 0, 0, tzinfo=UTC)
    mapping = {
        "sample_time": t0,
        "time_over": t0,
        "flight_id": "Z9",
        "aircraft_type": None,
        "origin": None,
        "destination": None,
        "lat": None,
        "lon": None,
        "flight_level": None,
        "route_string": None,
    }
    row = _denormalized_row_from_mapping(mapping)
    assert row.lat is None
    assert row.lon is None
    assert row.flight_level is None
