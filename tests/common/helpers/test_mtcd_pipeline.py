"""Tests for MTCD pipeline time alignment."""
# pylint: disable=protected-access

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from common.helpers.mtcd_pipeline import MtcdPipeline
from common.models.flight_position_adapter import FlightPositionAdapter


def _make_adapter(
        ts: datetime | None,
        lat: float,
        lon: float,
        flight_id: str,
        route: str | None,
        track_heading: int = 90,
) -> FlightPositionAdapter:
    """Build a FlightPositionAdapter backed by SimpleNamespace."""
    ns = SimpleNamespace(
        ts=ts,
        lat=lat,
        lon=lon,
        flight_level=280,
        ground_speed_kt=300,
        heading=track_heading,
        track_heading=track_heading,
        route=route,
        vertical_rate_fpm=0,
    )
    return FlightPositionAdapter(ns, flight_id)


def test_align_skips_when_skew_below_threshold() -> None:
    """No alignment when skew is at most TIME_SKEW_SYNC_THRESHOLD_SECONDS."""
    base = datetime.now(timezone.utc)
    pipeline = MtcdPipeline()
    f1 = _make_adapter(base, 50.0, 14.0, "A", None)
    f2 = _make_adapter(base + timedelta(seconds=5), 51.0, 15.0, "B", None)
    o1, o2 = pipeline._align_positions_to_common_time(f1, f2)
    assert o1 is f1
    assert o2 is f2


def test_align_extrapolates_kinematic_when_no_route() -> None:
    """Older sample is moved forward along velocity when skew > threshold."""
    t_new = datetime.now(timezone.utc)
    t_old = t_new - timedelta(seconds=20)
    pipeline = MtcdPipeline()
    f1 = _make_adapter(t_old, 50.0, 14.0, "A", None, track_heading=90)
    f2 = _make_adapter(t_new, 51.0, 15.0, "B", None)
    o1, o2 = pipeline._align_positions_to_common_time(f1, f2)
    assert o2 is f2
    assert o1.ts == t_new
    assert o1.lon > 14.0


def test_align_skips_when_timestamp_missing() -> None:
    """If either timestamp is missing, adapters are returned unchanged."""
    pipeline = MtcdPipeline()
    f1 = _make_adapter(None, 50.0, 14.0, "A", None)
    f2 = _make_adapter(datetime.now(timezone.utc), 51.0, 15.0, "B", None)
    o1, o2 = pipeline._align_positions_to_common_time(f1, f2)
    assert o1 is f1
    assert o2 is f2
