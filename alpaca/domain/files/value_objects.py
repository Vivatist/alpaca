from typing import Optional
from pydantic import BaseModel


class FileID(BaseModel):
    """Value object identifying a file via hash+path."""

    hash: Optional[str]
    path: str

    class Config:
        frozen = True
