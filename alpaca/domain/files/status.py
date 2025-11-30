from enum import Enum


class FileStatus(str, Enum):
    """Lifecycle statuses for monitored files."""

    ADDED = "added"
    UPDATED = "updated"
    DELETED = "deleted"
    PROCESSED = "processed"
    OK = "ok"
    ERROR = "error"

    @classmethod
    def queue_statuses(cls) -> tuple[str, ...]:
        return (cls.DELETED.value, cls.UPDATED.value, cls.ADDED.value)
