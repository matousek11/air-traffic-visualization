"""
Place for dataset streaming API
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx

from common.helpers.postgres_engine import create_postgres_engine_from_env
from common.helpers.logging_service import LoggingService
from dataset_stream.helpers.datasets import DatasetImportNameConflictError
from dataset_stream.helpers.datasets import DatasetNameNotFoundError
from dataset_stream.helpers.datasets import get_importable_datasets
from dataset_stream.helpers.datasets import get_importable_folders
from dataset_stream.helpers.datasets import list_csv_files_in_folder
from dataset_stream.helpers.datasets import resolve_import_target
from dataset_stream.import_script.importer import ImportResult
from dataset_stream.import_script.importer import import_flight_positions_csv
from dataset_stream.import_script.importer import import_flight_positions_csv_dir
from dataset_stream.request_models import ReplayStartRequest
from dataset_stream.request_models import ReplaySpeedRequest
from dataset_stream.response_models import DatasetImportOption
from dataset_stream.response_models import DatasetImportResponse
from dataset_stream.response_models import ReplayStatusResponse
from dataset_stream.services.replay_controller import ReplayController

logger = LoggingService.get_logger(__name__)

DATASETS_DIR = Path(__file__).resolve().parent / "datasets"
DEFAULT_TABLE_NAME = "dataset_flight_positions"

app = FastAPI()

_engine = create_postgres_engine_from_env()
replay_controller = ReplayController(
    engine=_engine,
    dataset_table_name=DEFAULT_TABLE_NAME,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace it with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(
    "/datasets/import-options",
    summary="List importable CSV files and CSV folders",
    description=(
        "Returns top-level CSV files and subdirectories that contain at least "
        "one CSV (non-recursive)."
    ),
    response_description=(
        "Sorted import options (file stem or folder name as id)."
    ),
    tags=["datasets"],
)
def get_dataset_import_options() -> list[DatasetImportOption]:
    """List datasets and importable folders under dataset_stream/datasets.

    Returns:
        Options with ids, labels, and kind (file or folder).
    """
    importable_filenames = get_importable_datasets(DATASETS_DIR)
    folder_names = get_importable_folders(DATASETS_DIR)
    file_stems = {Path(fn).stem for fn in importable_filenames}
    options: list[DatasetImportOption] = []
    for filename in importable_filenames:
        stem = Path(filename).stem
        options.append(
            DatasetImportOption(
                id=stem,
                label=stem,
                kind="file",
            ),
        )
    for name in folder_names:
        if name in file_stems:
            continue
        options.append(
            DatasetImportOption(
                id=name,
                label=f"{name} (folder)",
                kind="folder",
            ),
        )
    options.sort(key=lambda item: item.label.lower())
    return options


@app.post(
    "/datasets/{dataset_name}/import",
    summary="Import selected dataset to database",
    description=(
        "Runs import for one option from GET /datasets/import-options. "
        "Pass the CSV stem (no .csv) or the folder name, same path shape "
        "for both."
    ),
    response_description=(
        "Import execution summary including imported/skipped rows."
    ),
    tags=["datasets"],
)
def import_selected_dataset(
    dataset_name: str,
) -> DatasetImportResponse:
    """Import one CSV file or all CSVs in a folder into the denormalized table.

    Args:
        dataset_name: CSV stem, folder name, or legacy ``dir/<folder>`` form.

    Returns:
        Summary of import results.

    Raises:
        HTTPException: When the dataset name is not available or import fails.
    """
    importable_filenames = get_importable_datasets(DATASETS_DIR)
    folder_names = get_importable_folders(DATASETS_DIR)
    try:
        target = resolve_import_target(
            dataset_name,
            datasets_dir=DATASETS_DIR,
            importable_filenames=importable_filenames,
            importable_folder_names=folder_names,
        )
    except DatasetImportNameConflictError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except DatasetNameNotFoundError as error:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid dataset_name. Use GET /datasets/import-options for "
                "allowed CSV stems and folder names."
            ),
        ) from error

    engine = create_postgres_engine_from_env()
    try:
        if target.kind == "file":
            result: ImportResult = import_flight_positions_csv(
                csv_path=target.path,
                table_name=DEFAULT_TABLE_NAME,
                engine=engine,
            )
            return DatasetImportResponse(
                dataset_name=target.path.name,
                table_name=DEFAULT_TABLE_NAME,
                rows_imported=result.rows_imported,
                rows_skipped=result.rows_skipped,
                source_files=None,
            )

        result = import_flight_positions_csv_dir(
            dir_path=target.path,
            table_name=DEFAULT_TABLE_NAME,
            engine=engine,
        )
        source_files = [p.name for p in list_csv_files_in_folder(target.path)]
        return DatasetImportResponse(
            dataset_name=target.path.name,
            table_name=DEFAULT_TABLE_NAME,
            rows_imported=result.rows_imported,
            rows_skipped=result.rows_skipped,
            source_files=source_files,
        )
    except (ValueError, FileNotFoundError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    finally:
        engine.dispose()


@app.post(
    "/replay/start",
    response_model=ReplayStatusResponse,
    tags=["replay"],
)
def start_replay(request: ReplayStartRequest) -> ReplayStatusResponse:
    """Start replay worker."""
    try:
        return replay_controller.start(
            speed=request.speed,
            tick_interval_seconds=request.tick_interval_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post(
    "/replay/stop",
    response_model=ReplayStatusResponse,
    tags=["replay"],
)
def stop_replay() -> ReplayStatusResponse:
    """Stop replay worker."""
    return replay_controller.stop()


@app.get(
    "/replay/status",
    response_model=ReplayStatusResponse,
    tags=["replay"],
)
def get_replay_status() -> ReplayStatusResponse:
    """Get replay controller status."""
    return replay_controller.status()


@app.post(
    "/replay/speed",
    response_model=ReplayStatusResponse,
    tags=["replay"],
)
def set_replay_speed(request: ReplaySpeedRequest) -> ReplayStatusResponse:
    """Increase or decrease replay speed by 1 unit (minimum 1)."""
    try:
        return replay_controller.adjust_speed(increase=request.increase)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post(
    "/replay/reset",
    response_model=ReplayStatusResponse,
    tags=["replay"],
)
def reset_replay() -> ReplayStatusResponse:
    """Stop replay and reset the app DB state."""
    try:
        return replay_controller.reset()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reset database: {str(exc)}",
        ) from exc
