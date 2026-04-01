"""Tests for flight_plan_json attachment during dataset import."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

from dataset_stream.import_script.flight_plan_import import attach_flight_plans_or_skip
from dataset_stream.services.replay_types import DatasetSnapshotRow


def _base_row(
    *,
    route_string: str | None,
    lat: float | None = 50.0,
    lon: float | None = 14.0,
) -> DatasetSnapshotRow:
    """Build a snapshot row for tests."""
    t0 = datetime(2026, 3, 21, 16, 0, 0, tzinfo=UTC)
    return DatasetSnapshotRow(
        sample_time=t0,
        time_over=t0,
        flight_id="F1",
        aircraft_type="B738",
        origin="LKPR",
        destination=None,
        lat=lat,
        lon=lon,
        flight_level=100,
        route_string=route_string,
    )


def test_empty_route_sets_null_flight_plan() -> None:
    """Rows without a route get flight_plan_json None without calling expand."""
    rows = [_base_row(route_string=None)]
    with patch(
        "dataset_stream.import_script.flight_plan_import.expand_route_to_waypoint_names",
    ) as mock_expand:
        out, extra = attach_flight_plans_or_skip(rows)
        mock_expand.assert_not_called()
    assert len(out) == 1
    assert out[0].flight_plan_json is None
    assert extra == 0


def test_expand_success_sets_names() -> None:
    """Non-empty route uses expand output and cache."""
    rows = [
        _base_row(route_string="ABCDE ABCDE"),
    ]
    with patch(
        "dataset_stream.import_script.flight_plan_import.expand_route_to_waypoint_names",
        return_value=["A", "B"],
    ) as mock_expand:
        out, extra = attach_flight_plans_or_skip(rows)
        mock_expand.assert_called_once()
    assert extra == 0
    assert out[0].flight_plan_json == ["A", "B"]


def test_expand_failure_skips_row() -> None:
    """When expand returns None, the row is dropped and skip count increases."""
    rows = [_base_row(route_string="XYZ")]
    with patch(
        "dataset_stream.import_script.flight_plan_import.expand_route_to_waypoint_names",
        return_value=None,
    ):
        out, extra = attach_flight_plans_or_skip(rows)
    assert out == []
    assert extra == 1


def test_missing_position_skips_row_with_route() -> None:
    """Route without lat/lon cannot be expanded; row is skipped."""
    rows = [
        _base_row(route_string="ABC", lat=None, lon=14.0),
    ]
    with patch(
        "dataset_stream.import_script.flight_plan_import.expand_route_to_waypoint_names",
    ) as mock_expand:
        out, extra = attach_flight_plans_or_skip(rows)
        mock_expand.assert_not_called()
    assert out == []
    assert extra == 1


def test_cache_avoids_second_expand_call() -> None:
    """Same flight_id and route_string uses cache for subsequent rows."""
    t0 = datetime(2026, 3, 21, 16, 0, 0, tzinfo=UTC)
    t1 = datetime(2026, 3, 21, 16, 1, 0, tzinfo=UTC)
    route = "SAME ROUTE"
    rows = [
        DatasetSnapshotRow(
            sample_time=t0,
            time_over=t0,
            flight_id="F1",
            aircraft_type=None,
            origin=None,
            destination=None,
            lat=50.0,
            lon=14.0,
            flight_level=100,
            route_string=route,
        ),
        DatasetSnapshotRow(
            sample_time=t1,
            time_over=t1,
            flight_id="F1",
            aircraft_type=None,
            origin=None,
            destination=None,
            lat=50.1,
            lon=14.1,
            flight_level=100,
            route_string=route,
        ),
    ]
    with patch(
        "dataset_stream.import_script.flight_plan_import.expand_route_to_waypoint_names",
        return_value=["W1", "W2"],
    ) as mock_expand:
        out, extra = attach_flight_plans_or_skip(rows)
        assert mock_expand.call_count == 1
    assert extra == 0
    assert out[0].flight_plan_json == ["W1", "W2"]
    assert out[1].flight_plan_json == ["W1", "W2"]
