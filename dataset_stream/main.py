"""
Place for dataset streaming API
"""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from common.helpers.logging_service import LoggingService
from dataset_stream.helpers.datasets import get_importable_datasets

logger = LoggingService.get_logger(__name__)

DATABASE_SERVICE_URL = os.getenv("DATABASE_SERVICE_URL")
DATASETS_DIR = Path(__file__).resolve().parent / "datasets"

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
    summary="List importable dataset files",
    description=(
        "Returns all files that are "
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
    return get_importable_datasets(DATASETS_DIR)

