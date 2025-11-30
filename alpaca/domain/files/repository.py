from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Dict, List, Optional, Iterable, Any

from .value_objects import FileID
from .status import FileStatus
from .models import FileQueueItem


class FileRepository(ABC):
    """Persistence boundary for monitored files and derived chunks."""

    def __init__(self, database_url: str):  # pragma: no cover - subclasses may extend
        if not database_url:
            raise ValueError("database_url is required")
        self.connection_string = database_url

    @abstractmethod
    @contextmanager
    def get_connection(self):
        """Provide raw DB connection for low-level consumers (legacy compatibility)."""
        raise NotImplementedError

    # --- Status / queue operations -------------------------------------------------
    @abstractmethod
    def get_processed_count(self) -> int:
        pass

    @abstractmethod
    def get_pending_files(self) -> Dict[str, List[FileID]]:
        pass

    @abstractmethod
    def mark_as_processed(self, file_hash: str) -> bool:
        pass

    @abstractmethod
    def mark_as_ok(self, file_hash: str) -> bool:
        pass

    @abstractmethod
    def mark_as_error(self, file_hash: str) -> bool:
        pass

    @abstractmethod
    def reset_processed_to_status(self, target_status: FileStatus = FileStatus.ADDED) -> int:
        pass

    @abstractmethod
    def get_next_file_for_processing(self) -> Optional[FileQueueItem]:
        pass

    @abstractmethod
    def get_queue_stats(self) -> Dict[str, int]:
        pass

    # --- File lifecycle -----------------------------------------------------------
    @abstractmethod
    def delete_file_by_hash(self, file_hash: str) -> bool:
        pass

    @abstractmethod
    def set_raw_text(self, file_hash: str, raw_text: str) -> bool:
        pass

    # --- Chunk operations ---------------------------------------------------------
    @abstractmethod
    def delete_chunks_by_hash(self, file_hash: str) -> int:
        pass

    @abstractmethod
    def delete_chunks_by_path(self, file_path: str) -> int:
        pass

    @abstractmethod
    def get_chunks_by_hash(self, file_hash: str) -> List[tuple]:
        pass

    @abstractmethod
    def save_chunk(self, content: str, metadata: dict, embedding: Optional[List[float]] = None) -> bool:
        pass

    @abstractmethod
    def get_chunks_count(self, file_hash: str) -> int:
        pass

    # --- Synchronization utilities (used by file watcher) -------------------------
    @abstractmethod
    def sync_by_hash(self, disk_files: List[Dict[str, Any]]) -> Dict[str, int]:
        pass

    @abstractmethod
    def get_file_state_records(self) -> List[tuple]:
        pass

    @abstractmethod
    def get_documents_records(self) -> List[tuple]:
        pass

    @abstractmethod
    def update_status_sync_batch(self, updates: Iterable[tuple[str, str]]) -> int:
        pass


# Backwards-compatible alias with old naming -------------------------------------------------
class Database(FileRepository):
    pass
