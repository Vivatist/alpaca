from typing import Optional
from pydantic import BaseModel, ConfigDict


class FileID(BaseModel):
    """Value object identifying a file via hash+path."""

    hash: Optional[str]
    path: str

    model_config = ConfigDict(frozen=True)
