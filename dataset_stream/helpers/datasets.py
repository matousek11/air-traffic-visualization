"""Dataset helper utilities for import API."""

from pathlib import Path

from common.helpers.logging_service import LoggingService

logger = LoggingService.get_logger(__name__)

IMPORTABLE_EXTENSIONS = {".csv", ".xml", ".json"}


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
        if file_path.is_file() and file_path.suffix.lower() in IMPORTABLE_EXTENSIONS:
            importable_files.append(file_path.name)

    return sorted(importable_files)
