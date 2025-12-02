from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Any

from core.domain.files import FileStatus, FileQueueItem
from core.domain.files.repository import FileRepository


@dataclass
class ResetStuckFiles:
    """Reset lingering 'processed' states back to queue."""

    repo: FileRepository
    target_status: FileStatus = FileStatus.ADDED

    def __call__(self) -> int:
        return self.repo.reset_processed_to_status(self.target_status)


@dataclass
class DequeueNextFile:
    """Fetch next file for processing respecting priority order."""

    repo: FileRepository

    def __call__(self) -> Optional[FileQueueItem]:
        return self.repo.get_next_file_for_processing()


@dataclass
class GetQueueStats:
    """Retrieve aggregated queue stats for monitoring."""

    repo: FileRepository

    def __call__(self) -> Dict[str, int]:
        return self.repo.get_queue_stats()


@dataclass
class SyncFilesystemSnapshot:
    """Persist results of disk scan provided by FileWatcher."""

    repo: FileRepository

    def __call__(self, files: List[Dict[str, Any]]) -> Dict[str, int]:
        return self.repo.sync_by_hash(files)
