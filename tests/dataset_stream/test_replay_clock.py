from __future__ import annotations

from datetime import UTC, datetime, timedelta

from dataset_stream.services.replay_clock import ReplayClock


def test_replay_clock_advances_by_tick_times_speed() -> None:
    """ReplayClock must advance sim time by tick_interval * speed."""
    dataset_min = datetime(2026, 1, 1, tzinfo=UTC)
    dataset_max = dataset_min + timedelta(minutes=10)

    clock = ReplayClock(
        dataset_min_time=dataset_min,
        dataset_max_time=dataset_max,
        speed=2.0,
        tick_interval_seconds=5.0,
    )

    assert clock.state.current_tick_sim_time == dataset_min
    clock.advance_one_tick()
    assert clock.state.current_tick_sim_time == dataset_min + timedelta(seconds=10)


def test_replay_clock_set_speed_applies_to_next_advance() -> None:
    """Speed update should apply only to the next tick advancement."""
    dataset_min = datetime(2026, 1, 1, tzinfo=UTC)
    dataset_max = dataset_min + timedelta(minutes=10)

    clock = ReplayClock(
        dataset_min_time=dataset_min,
        dataset_max_time=dataset_max,
        speed=1.0,
        tick_interval_seconds=5.0,
    )

    clock.advance_one_tick()
    assert clock.state.current_tick_sim_time == dataset_min + timedelta(seconds=5)

    clock.set_speed(3.0)
    clock.advance_one_tick()
    assert clock.state.current_tick_sim_time == dataset_min + timedelta(seconds=20)


def test_replay_clock_progress_is_clamped_to_dataset_max() -> None:
    """Progress percent should be clamped to [0, 100]."""
    dataset_min = datetime(2026, 1, 1, tzinfo=UTC)
    dataset_max = dataset_min + timedelta(seconds=100)

    clock = ReplayClock(
        dataset_min_time=dataset_min,
        dataset_max_time=dataset_max,
        speed=1.0,
        tick_interval_seconds=5.0,
    )

    assert clock.progress_percent == 0.0

    clock.state.current_tick_sim_time = dataset_max
    assert clock.progress_percent == 100.0

    clock.state.current_tick_sim_time = dataset_max + timedelta(seconds=1)
    assert clock.progress_percent == 100.0

