"""
Place for dataset streaming API
"""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware

from common.helpers.postgres_engine import create_postgres_engine_from_env
from common.helpers.logging_service import LoggingService
from dataset_stream.helpers.datasets import DatasetNameNotFoundError
from dataset_stream.helpers.datasets import get_importable_datasets
from dataset_stream.helpers.datasets import resolve_dataset_filename
from dataset_stream.import_script.importer import ImportResult
from dataset_stream.import_script.importer import import_flight_positions_csv
from dataset_stream.response_models import DatasetImportResponse

logger = LoggingService.get_logger(__name__)

DATABASE_SERVICE_URL = os.getenv("DATABASE_SERVICE_URL")
DATASETS_DIR = Path(__file__).resolve().parent / "datasets"
DEFAULT_TABLE_NAME = "dataset_flight_positions"

app = FastAPI()

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
    summary="List importable CSV dataset files",
    description=(
        "Returns all CSV files that are "
        "supported by the import pipeline."
    ),
    response_description="Alphabetically sorted list of dataset filenames.",
    tags=["datasets"],
)
def get_dataset_import_options() -> list[str]:
    """Get a list of available datasets that can be imported to a database.

    Returns:
        List of importable dataset filenames from dataset_stream/datasets.
    """
    importable_datasets = get_importable_datasets(DATASETS_DIR)
    return [Path(filename).stem for filename in importable_datasets]


@app.post(
    "/datasets/{dataset_name}/import",
    summary="Import selected dataset to database",
    description=(
        "Runs import pipeline "
        "for one selected dataset from the available import options. "
        "The `dataset_name` path parameter is expected without file extension."
    ),
    response_description="Import execution summary including imported/skipped rows.",
    tags=["datasets"],
)
def import_selected_dataset(
    dataset_name: str,
) -> DatasetImportResponse:
    """Import one selected dataset into the denormalized table.

    Args:
        dataset_name: CSV dataset base name (without .csv extension).

    Returns:
        Summary of import results.

    Raises:
        HTTPException: When the dataset name is not available or import fails.
    """
    importable_datasets = get_importable_datasets(DATASETS_DIR)
    try:
        resolved_dataset_filename = resolve_dataset_filename(
            dataset_name,
            importable_datasets,
        )
    except DatasetNameNotFoundError as error:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid dataset_name. Send dataset name without extension and "
                "use GET /datasets/import-options to list available datasets."
            ),
        ) from error

    csv_path = DATASETS_DIR / resolved_dataset_filename
    try:
        engine = create_postgres_engine_from_env()
        result: ImportResult = import_flight_positions_csv(
            csv_path=csv_path,
            table_name=DEFAULT_TABLE_NAME,
            engine=engine,
        )
        engine.dispose()
    except (ValueError, FileNotFoundError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return DatasetImportResponse(
        dataset_name=resolved_dataset_filename,
        table_name=DEFAULT_TABLE_NAME,
        rows_imported=result.rows_imported,
        rows_skipped=result.rows_skipped,
    )

