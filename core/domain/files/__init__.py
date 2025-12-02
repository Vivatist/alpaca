"""
Доменные объекты для работы с файлами и их жизненным циклом.

=== НАЗНАЧЕНИЕ ===
Модуль экспортирует основные сущности для отслеживания файлов в системе:
- FileSnapshot — полное представление файла с метаданными и raw_text
- FileQueueItem — элемент очереди обработки
- FileID — value object для идентификации файла (hash + path)
- FileStatus — перечисление статусов синхронизации
- FileRepository/Database — интерфейс для работы с хранилищем

=== ЖИЗНЕННЫЙ ЦИКЛ СТАТУСОВ ===
    added/updated/deleted  →  processed  →  ok/error
          ↑                                    ↓
          └─────────── (retry) ────────────────┘

=== ИСПОЛЬЗОВАНИЕ ===

    from core.domain.files import FileSnapshot, FileStatus, FileRepository

    # Создать снимок файла
    file = FileSnapshot(
        path="docs/report.docx",
        hash="abc123...",
        status_sync=FileStatus.ADDED,
        size=102400
    )

    # Получить полный путь
    print(file.full_path)  # /home/alpaca/monitored_folder/docs/report.docx

    # Использовать репозиторий (через DI)
    def process(file: FileSnapshot, repo: FileRepository):
        repo.mark_as_ok(file)

=== МОДЕЛИ ===
- FileSnapshot: path, hash, status_sync, size, raw_text, mtime, last_checked
- FileQueueItem: hash, path, status_sync (минимум для очереди)
- FileID: hash, path (идентификация)
"""

from .status import FileStatus
from .value_objects import FileID
from .models import FileQueueItem, FileSnapshot
from .repository import FileRepository, Database

__all__ = [
    "FileStatus",
    "FileID",
    "FileQueueItem",
    "FileSnapshot",
    "FileRepository",
    "Database",
]
