"""Dataset helper utilities for import API."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from common.helpers.logging_service import LoggingService

logger = LoggingService.get_logger(__name__)

IMPORTABLE_EXTENSIONS = {".csv"}


class DatasetNameNotFoundError(ValueError):
    """Raised when the dataset base name has no matching file or folder."""


class DatasetImportNameConflictError(ValueError):
    """Raised when the same name matches both a CSV file and a folder."""


@dataclass(frozen=True)
class ResolvedImportTarget:
    """Filesystem target for a dataset import request."""

    kind: Literal["file", "folder"]
    path: Path


def get_importable_datasets(datasets_dir: Path) -> list[str]:
    """Return importable dataset files from the datasets directory.

    Args:
        datasets_dir: Directory containing candidate dataset files.

    Returns:
        List of importable dataset filenames sorted alphabetically.
    """
    if not datasets_dir.exists():
        logger.warning("Datasets directory does not exist: %s", datasets_dir)
        return []

    importable_files: list[str] = []
    for file_path in datasets_dir.iterdir():
        suffix_ok = file_path.suffix.lower() in IMPORTABLE_EXTENSIONS
        if file_path.is_file() and suffix_ok:
            importable_files.append(file_path.name)

    return sorted(importable_files)


def get_importable_folders(datasets_dir: Path) -> list[str]:
    """Return names of top-level subdirectories that contain at least one CSV.

    Args:
        datasets_dir: Root datasets directory.

    Returns:
        Sorted list of subdirectory names (single path segment each).
    """
    if not datasets_dir.exists():
        logger.warning("Datasets directory does not exist: %s", datasets_dir)
        return []

    folder_names: list[str] = []
    for child in datasets_dir.iterdir():
        if not child.is_dir():
            continue
        has_csv = any(
            p.is_file() and p.suffix.lower() in IMPORTABLE_EXTENSIONS
            for p in child.glob("*.csv")
        )
        if has_csv:
            folder_names.append(child.name)

    return sorted(folder_names)


def resolve_dataset_filename(
    dataset_name: str,
    importable_datasets: list[str],
) -> str:
    """Resolve the dataset base name to an available CSV filename.

    Args:
        dataset_name: Dataset name without extension.
        importable_datasets: Available importable filenames.

    Returns:
        Resolved CSV filename including extension.

    Raises:
        DatasetNameNotFoundError: When the dataset name has no match.
    """
    resolved_filename = f"{dataset_name}.csv"
    if resolved_filename not in importable_datasets:
        raise DatasetNameNotFoundError(dataset_name)
    return resolved_filename


def resolve_import_target(
    dataset_name: str,
    *,
    datasets_dir: Path,
    importable_filenames: list[str],
    importable_folder_names: list[str],
) -> ResolvedImportTarget:
    """Resolve an API dataset id to a file or directory path under datasets_dir.

    Args:
        dataset_name: CSV stem or folder name.
        datasets_dir: Root datasets directory.
        importable_filenames: Basenames from :func:`get_importable_datasets`.
        importable_folder_names: Names from :func:`get_importable_folders`.

    Returns:
        Target kind and absolute path to the CSV file or folder.

    Raises:
        DatasetNameNotFoundError: When the id does not match a known option.
        DatasetImportNameConflictError: When both ``name.csv`` and folder
            ``name`` exist and are importable.
    """
    has_file = f"{dataset_name}.csv" in importable_filenames
    has_folder = dataset_name in importable_folder_names
    if has_file and has_folder:
        msg = (
            f"Ambiguous dataset name {dataset_name!r}: both {dataset_name}.csv "
            "and folder exist."
        )
        raise DatasetImportNameConflictError(msg)
    if has_file:
        return ResolvedImportTarget(
            kind="file",
            path=(datasets_dir / f"{dataset_name}.csv").resolve(),
        )
    if has_folder:
        return ResolvedImportTarget(
            kind="folder",
            path=(datasets_dir / dataset_name).resolve(),
        )
    raise DatasetNameNotFoundError(dataset_name)


def list_csv_files_in_folder(folder: Path) -> list[Path]:
    """Return sorted paths to ``*.csv`` files directly inside ``folder``.

    Args:
        folder: Directory to scan (non-recursive).

    Returns:
        Sorted list of CSV file paths.
    """
    paths = [p for p in folder.glob("*.csv") if p.is_file()]
    return sorted(paths, key=lambda p: p.name)
