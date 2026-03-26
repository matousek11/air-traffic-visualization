"""CLI entry point: python -m dataset_stream.import_script."""

# pylint: disable=invalid-name

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from common.helpers.postgres_engine import create_postgres_engine_from_env
from dataset_stream.import_script.importer import import_flight_positions_csv

DEFAULT_TABLE = "dataset_flight_positions"


def _default_csv_path() -> Path:
    """Return the path to the bundled sample CSV under dataset_stream."""
    here = Path(__file__).resolve().parent.parent
    return here / "datasets" / "flight_positions_10.csv"


def main() -> None:
    """Parse CLI arguments and run the import."""
    parser = argparse.ArgumentParser(
        prog="python -m dataset_stream.import_script",
        description=(
            "Import NM B2B-style flight_positions CSV into a denormalized "
            "Timescale hypertable."
        ),
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=_default_csv_path(),
        help=(
            "Path to CSV (default: bundled flight_positions_10.csv "
            "under dataset_stream/datasets/)"
        ),
    )
    args = parser.parse_args()
    engine = create_postgres_engine_from_env()
    result = import_flight_positions_csv(
        csv_path=args.csv,
        table_name=args.table,
        engine=engine,
    )
    logging.getLogger(__name__).info(
        "Done: imported=%s skipped=%s",
        result.rows_imported,
        result.rows_skipped,
    )


if __name__ == "__main__":
    main()
    sys.exit(0)
