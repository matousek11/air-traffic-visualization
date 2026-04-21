"""Response model for dataset import listing."""

from typing import Literal

from pydantic import BaseModel


class DatasetImportOption(BaseModel):
    """One selectable CSV file or folder under the datasets root."""

    id: str
    label: str
    kind: Literal["file", "folder"]
