"""Record periodic NM B2B flight snapshots into CSV files.

Usage as CLI::

    python flight_dataset_creator.py \
        --airspace LK \
        --duration 10m \
        --output-dir ./output

The recorder uses a static B2B traffic window from the script start time to the
planned script end time. It polls every 5 seconds by default, writes normalized
flight snapshots into CSV, logs remaining runtime, and can be stopped early via
``Ctrl+C``.
"""

from __future__ import annotations

import argparse
import csv
import logging
import signal
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from threading import Event
from typing import TextIO

from flights_in_airspace_data_retrieval import (
    B2BConfig,
    B2BError,
    DEFAULT_ROUTE_FIELD,
    ROUTE_FIELD_FILED,
    ROUTE_FIELD_ICAO,
    FlightRecord,
    fetch_flight_records_in_airspaces,
)

log = logging.getLogger(__name__)

DEFAULT_POLL_INTERVAL_S = 5.0
DEFAULT_OUTPUT_FILENAME = "flight_positions.csv"
CSV_FIELDNAMES = (
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


def _parse_duration(value: str) -> timedelta:
    """Parse duration strings like ``300s``, ``10m`` or ``2h``."""
    text = value.strip().lower()
    if not text:
        raise argparse.ArgumentTypeError("Duration must not be empty.")

    units = {
        "s": 1,
        "m": 60,
        "h": 3600,
    }
    suffix = text[-1]
    if suffix in units:
        number_text = text[:-1]
        multiplier = units[suffix]
    else:
        number_text = text
        multiplier = 1

    try:
        amount = float(number_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid duration value: {value!r}."
        ) from exc

    if amount <= 0:
        raise argparse.ArgumentTypeError("Duration must be greater than zero.")
    return timedelta(seconds=amount * multiplier)


def _positive_float(value: str) -> float:
    """Parse a positive float CLI argument."""
    try:
        number = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Expected a positive number, got {value!r}."
        ) from exc
    if number <= 0:
        raise argparse.ArgumentTypeError("Value must be greater than zero.")
    return number


def _format_remaining(delta: timedelta) -> str:
    """Format remaining runtime in ``HH:MM:SS``."""
    total_seconds = max(0, int(delta.total_seconds()))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _utcnow_naive() -> datetime:
    """Return the current UTC timestamp as a naive datetime."""
    return datetime.utcnow()


def _parse_iso_utc_minute_or_second(value: str | None) -> datetime | None:
    """Parse an ISO UTC timestamp produced by the retrieval service."""
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _stringify_csv_value(value: object) -> str:
    """Convert optional values into CSV-friendly strings."""
    if value is None:
        return ""
    return str(value)


def _record_to_csv_row(record: FlightRecord) -> dict[str, str]:
    """Serialize one normalized flight record into the CSV contract."""
    return {
        "sample_time": _stringify_csv_value(record.sample_time),
        "time_over": _stringify_csv_value(record.time_over),
        "flight_id": _stringify_csv_value(record.flight_id),
        "aircraft_type": _stringify_csv_value(record.aircraft_type),
        "origin": _stringify_csv_value(record.origin),
        "destination": _stringify_csv_value(record.destination),
        "lat": _stringify_csv_value(record.lat),
        "lon": _stringify_csv_value(record.lon),
        "flight_level": _stringify_csv_value(record.flight_level),
        "route_string": _stringify_csv_value(record.route_string),
    }


@dataclass
class CsvTarget:
    """Active CSV file handle and writer."""

    path: Path
    handle: TextIO
    writer: csv.DictWriter


class CsvRecorder:
    """Manage CSV file creation, rotation and flush semantics."""

    def __init__(
        self,
        *,
        output_dir: Path | None,
        csv_path: Path | None,
        hourly_rotation_enabled: bool,
    ) -> None:
        self.output_dir = output_dir
        self.csv_path = csv_path
        self.hourly_rotation_enabled = hourly_rotation_enabled
        self._current_key: str | None = None
        self._target: CsvTarget | None = None

    def close(self) -> None:
        """Close the current CSV file if it is open."""
        if self._target is None:
            return
        self._target.handle.flush()
        self._target.handle.close()
        self._target = None
        self._current_key = None

    def prepare_for_cycle(self, cycle_time: datetime) -> Path:
        """Ensure the correct CSV file is open for the given cycle."""
        key = self._build_rotation_key(cycle_time)
        if key == self._current_key and self._target is not None:
            return self._target.path

        self.close()
        path = self._resolve_path(cycle_time)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_exists = path.exists()
        handle = path.open("a", newline="", encoding="utf-8")
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDNAMES)
        if not file_exists or path.stat().st_size == 0:
            writer.writeheader()
            handle.flush()

        self._target = CsvTarget(path=path, handle=handle, writer=writer)
        self._current_key = key
        log.info("Writing CSV output to %s.", path)
        return path

    def write_records(self, records: Sequence[FlightRecord], cycle_time: datetime) -> int:
        """Write all records from one poll cycle and flush immediately."""
        self.prepare_for_cycle(cycle_time)
        if self._target is None:
            return 0

        for record in records:
            self._target.writer.writerow(_record_to_csv_row(record))
        self._target.handle.flush()
        return len(records)

    def _build_rotation_key(self, cycle_time: datetime) -> str:
        if not self.hourly_rotation_enabled:
            return "single-file"
        return cycle_time.strftime("%Y-%m-%d-%H")

    def _resolve_path(self, cycle_time: datetime) -> Path:
        if self.hourly_rotation_enabled:
            return self._resolve_hourly_path(cycle_time)
        if self.csv_path is not None:
            return self.csv_path
        assert self.output_dir is not None  # for type checkers
        return self.output_dir / DEFAULT_OUTPUT_FILENAME

    def _resolve_hourly_path(self, cycle_time: datetime) -> Path:
        stamp = cycle_time.strftime("%Y-%m-%d_%H")
        if self.csv_path is not None:
            suffix = self.csv_path.suffix or ".csv"
            return self.csv_path.with_name(f"{self.csv_path.stem}_{stamp}{suffix}")
        assert self.output_dir is not None  # for type checkers
        return self.output_dir / f"flight_positions_{stamp}.csv"


def build_argument_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser for the recorder."""
    parser = argparse.ArgumentParser(
        description=(
            "Poll NM B2B flight snapshots at a fixed interval and store the "
            "normalized records in CSV."
        )
    )
    parser.add_argument(
        "--airspace",
        action="append",
        default=[],
        help="Airspace identifier to poll (repeatable, default: LK).",
    )
    parser.add_argument(
        "--duration",
        type=_parse_duration,
        required=True,
        help="How long the recorder should run, e.g. 300s, 10m, 2h.",
    )
    parser.add_argument(
        "--interval-seconds",
        type=_positive_float,
        default=DEFAULT_POLL_INTERVAL_S,
        help="Polling interval in seconds (default: 5).",
    )
    parser.add_argument(
        "--redis-host",
        default="10.15.2.203",
        help="Redis proxy host.",
    )
    parser.add_argument(
        "--redis-port",
        type=int,
        default=6379,
        help="Redis proxy port.",
    )
    parser.add_argument(
        "--end-user-id",
        default="lukasm",
        help="NM B2B end user ID.",
    )
    parser.add_argument(
        "--channel-suffix",
        default=":1",
        help="Redis request/reply channel suffix.",
    )
    parser.add_argument(
        "--response-timeout",
        type=int,
        default=90,
        help="Timeout in seconds for one NM B2B reply.",
    )
    parser.add_argument(
        "--route-field",
        choices=(ROUTE_FIELD_ICAO, ROUTE_FIELD_FILED),
        default=DEFAULT_ROUTE_FIELD,
        help="Preferred route field requested from NM B2B.",
    )
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument(
        "--output-dir",
        default=".",
        help="Directory where CSV files will be created.",
    )
    output_group.add_argument(
        "--csv-path",
        help="Explicit CSV path for runs without hourly rotation; used as a filename base otherwise.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG-level logging.",
    )
    return parser


def _install_signal_handlers(stop_event: Event) -> None:
    """Install signal handlers that request graceful shutdown."""

    def _handle_signal(signum: int, _frame: object) -> None:
        signal_name = signal.Signals(signum).name
        if not stop_event.is_set():
            log.warning("%s received, stopping after the current cycle.", signal_name)
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, _handle_signal)


def _build_csv_recorder(args: argparse.Namespace, *, scheduled_duration: timedelta) -> CsvRecorder:
    """Create the CSV recorder based on CLI output settings."""
    hourly_rotation_enabled = scheduled_duration > timedelta(hours=1)
    csv_path = Path(args.csv_path).expanduser() if args.csv_path else None
    output_dir = None if csv_path is not None else Path(args.output_dir).expanduser()
    return CsvRecorder(
        output_dir=output_dir,
        csv_path=csv_path,
        hourly_rotation_enabled=hourly_rotation_enabled,
    )


def _pick_cycle_reference_time(cycle_start: datetime, records: Sequence[FlightRecord]) -> datetime:
    """Choose the time bucket used for CSV rotation."""
    if not records:
        return cycle_start
    sample_time = _parse_iso_utc_minute_or_second(records[0].sample_time)
    return sample_time or cycle_start


def run_recorder(args: argparse.Namespace) -> int:
    """Run the periodic polling loop until the scheduled end or interrupt."""
    script_start = _utcnow_naive()
    scheduled_end = script_start + args.duration
    config = B2BConfig(
        redis_host=args.redis_host,
        redis_port=args.redis_port,
        end_user_id=args.end_user_id,
        channel_suffix=args.channel_suffix,
        response_timeout_s=args.response_timeout,
    )
    airspaces = args.airspace or ["LK"]
    csv_recorder = _build_csv_recorder(args, scheduled_duration=args.duration)
    stop_event = Event()
    _install_signal_handlers(stop_event)

    cycle_index = 0
    try:
        log.info(
            "Starting flight dataset recorder: airspaces=%s interval=%.1fs window=%s .. %s (UTC).",
            ",".join(airspaces),
            args.interval_seconds,
            script_start.strftime("%Y-%m-%d %H:%M:%S"),
            scheduled_end.strftime("%Y-%m-%d %H:%M:%S"),
        )

        while not stop_event.is_set():
            now = _utcnow_naive()
            if now >= scheduled_end:
                log.info("Scheduled end reached, stopping recorder.")
                break

            cycle_index += 1
            cycle_started_monotonic = time.monotonic()
            remaining_before = scheduled_end - now
            log.info(
                "Cycle %d started, remaining runtime %s.",
                cycle_index,
                _format_remaining(remaining_before),
            )

            try:
                records = fetch_flight_records_in_airspaces(
                    airspaces=airspaces,
                    start_datetime=script_start,
                    end_datetime=scheduled_end,
                    config=config,
                    print_response=False,
                    requested_route_field=args.route_field,
                )
            except B2BError as exc:
                log.warning("Cycle %d failed due to NM B2B error: %s", cycle_index, exc)
                records = []
            except Exception:  # noqa: BLE001
                log.exception("Cycle %d failed unexpectedly.", cycle_index)
                records = []

            cycle_time = _pick_cycle_reference_time(now, records)
            written_rows = csv_recorder.write_records(records, cycle_time)

            cycle_elapsed = time.monotonic() - cycle_started_monotonic
            remaining_after = max(timedelta(0), scheduled_end - _utcnow_naive())
            log.info(
                "Cycle %d finished: %d row(s) written in %.2fs, remaining runtime %s.",
                cycle_index,
                written_rows,
                cycle_elapsed,
                _format_remaining(remaining_after),
            )

            if stop_event.is_set():
                break

            sleep_seconds = min(
                max(0.0, args.interval_seconds - cycle_elapsed),
                max(0.0, remaining_after.total_seconds()),
            )
            if cycle_elapsed > args.interval_seconds:
                log.warning(
                    "Cycle %d exceeded the polling interval by %.2fs.",
                    cycle_index,
                    cycle_elapsed - args.interval_seconds,
                )
                sleep_seconds = 0.0

            if sleep_seconds > 0 and stop_event.wait(timeout=sleep_seconds):
                break

        return 0
    finally:
        csv_recorder.close()


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    try:
        return run_recorder(args)
    except KeyboardInterrupt:
        log.warning("Keyboard interrupt received, exiting.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
