from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .status import FileStatus


@dataclass(slots=True)
class FileSnapshot:
    """Represents persisted metadata about a monitored file."""

    path: str
    hash: Optional[str]
    size: int
    status: Optional[str]
    mtime: Optional[float]
    last_checked: Optional[datetime]


@dataclass(slots=True)
class FileQueueItem:
    """Item returned by queue polling queries."""

    path: str
    hash: Optional[str]
    size: Optional[int]
    status: FileStatus
    last_checked: Optional[datetime]

    def as_dict(self) -> dict:
        return {
            "path": self.path,
            "hash": self.hash,
            "size": self.size,
            "status_sync": self.status.value,
            "last_checked": self.last_checked.isoformat() if self.last_checked else None,
        }
