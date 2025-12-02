from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from settings import settings

from .status import FileStatus


@dataclass(slots=True)
class FileSnapshot:
    """Сущность отслеживаемого файла, используемая по всему пайплайну."""

    path: str
    hash: str
    status_sync: str
    size: Optional[int] = None
    raw_text: Optional[str] = None
    mtime: Optional[float] = None
    last_checked: Optional[datetime] = None
    metadata: Optional[dict] = None  # Метаданные извлечённые metaextractor'oм

    @property
    def full_path(self) -> str:
        """Абсолютный путь до файла внутри monitored_folder."""
        return self.path if os.path.isabs(self.path) else os.path.join(settings.MONITORED_PATH, self.path)


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
