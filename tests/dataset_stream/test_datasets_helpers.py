"""Tests for dataset_stream.helpers.datasets."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from dataset_stream.helpers.datasets import DatasetImportNameConflictError
from dataset_stream.helpers.datasets import DatasetNameNotFoundError
from dataset_stream.helpers.datasets import get_importable_folders
from dataset_stream.helpers.datasets import list_csv_files_in_folder
from dataset_stream.helpers.datasets import resolve_import_target
from dataset_stream.import_script.importer import import_flight_positions_csv_dir


def test_get_importable_folders_skips_empty_and_non_csv(tmp_path: Path) -> None:
    """Only top-level folders with a direct CSV are listed."""
    (tmp_path / "empty_dir").mkdir()
    no_csv = tmp_path / "no_csv"
    no_csv.mkdir()
    (no_csv / "readme.txt").write_text("x", encoding="utf-8")

    has_csv = tmp_path / "has_csv"
    has_csv.mkdir()
    (has_csv / "a.csv").write_text("h\n", encoding="utf-8")

    nested = tmp_path / "nested"
    nested.mkdir()
    sub = nested / "sub"
    sub.mkdir()
    (sub / "b.csv").write_text("h\n", encoding="utf-8")

    names = get_importable_folders(tmp_path)
    assert names == ["has_csv"]
    assert "nested" not in names


def test_list_csv_files_in_folder_sorted(tmp_path: Path) -> None:
    """CSV basenames are sorted for stable import order."""
    (tmp_path / "z.csv").write_text("h\n", encoding="utf-8")
    (tmp_path / "a.csv").write_text("h\n", encoding="utf-8")

    paths = list_csv_files_in_folder(tmp_path)
    assert [p.name for p in paths] == ["a.csv", "z.csv"]


def test_resolve_import_target_file(tmp_path: Path) -> None:
    """File stem maps to CSV path."""
    (tmp_path / "sample.csv").write_text("x", encoding="utf-8")
    target = resolve_import_target(
        "sample",
        datasets_dir=tmp_path,
        importable_filenames=["sample.csv"],
        importable_folder_names=[],
    )
    assert target.kind == "file"
    assert target.path == (tmp_path / "sample.csv").resolve()


def test_resolve_import_target_folder(tmp_path: Path) -> None:
    """Folder name maps to folder path (same shape as file stem)."""
    folder = tmp_path / "run1"
    folder.mkdir()
    (folder / "x.csv").write_text("h\n", encoding="utf-8")

    target = resolve_import_target(
        "run1",
        datasets_dir=tmp_path,
        importable_filenames=[],
        importable_folder_names=["run1"],
    )
    assert target.kind == "folder"
    assert target.path == folder.resolve()


def test_resolve_import_target_rejects_slashes_in_name() -> None:
    """Path segments in dataset_name are invalid."""
    with pytest.raises(DatasetNameNotFoundError):
        resolve_import_target(
            "parent/child",
            datasets_dir=Path("/tmp"),
            importable_filenames=[],
            importable_folder_names=[],
        )


def test_resolve_import_target_conflict_raises(tmp_path: Path) -> None:
    """Same name as both CSV and folder is rejected."""
    (tmp_path / "dup.csv").write_text("x", encoding="utf-8")
    dup = tmp_path / "dup"
    dup.mkdir()
    (dup / "a.csv").write_text("h\n", encoding="utf-8")

    with pytest.raises(DatasetImportNameConflictError):
        resolve_import_target(
            "dup",
            datasets_dir=tmp_path,
            importable_filenames=["dup.csv"],
            importable_folder_names=["dup"],
        )


def test_import_flight_positions_csv_dir_empty_folder_no_db(
    tmp_path: Path,
) -> None:
    """No CSV files raises before using the database engine."""
    empty = tmp_path / "empty"
    empty.mkdir()
    engine = MagicMock()

    with pytest.raises(ValueError, match="No CSV files"):
        import_flight_positions_csv_dir(
            dir_path=empty,
            table_name="dataset_flight_positions",
            engine=engine,
        )
