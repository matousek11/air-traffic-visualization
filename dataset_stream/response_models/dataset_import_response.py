"""Response models for dataset import endpoints."""

from pydantic import BaseModel


class DatasetImportResponse(BaseModel):
    """Response payload with dataset import summary."""
    dataset_name: str
    table_name: str
    rows_imported: int
    rows_skipped: int
