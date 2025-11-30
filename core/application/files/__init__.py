"""
Use-case'ы для управления жизненным циклом файлов.

=== НАЗНАЧЕНИЕ ===
Модуль содержит use-case'ы для работы с очередью файлов:
- ResetStuckFiles — сброс зависших файлов в статусе 'processed'
- DequeueNextFile — получение следующего файла из очереди
- GetQueueStats — статистика очереди по статусам
- SyncFilesystemSnapshot — синхронизация с файловой системой
- FileService — сервис для операций с файлами

=== ИСПОЛЬЗОВАНИЕ ===

    from core.application.files import (
        ResetStuckFiles, DequeueNextFile, GetQueueStats, FileService
    )

    # Сбросить зависшие файлы при запуске worker'а
    reset = ResetStuckFiles(repository)
    reset()  # processed -> added/updated/deleted

    # Получить статистику очереди
    stats = GetQueueStats(repository)
    print(stats())  # {'added': 10, 'updated': 2, 'deleted': 1}

    # Извлечь следующий файл
    dequeue = DequeueNextFile(repository)
    file = dequeue()  # FileSnapshot или None

=== ПРИОРИТЕТЫ ОЧЕРЕДИ ===
1. deleted — удалённые файлы (нужно удалить чанки)
2. updated — изменённые (переобработать)
3. added — новые (обработать)
"""

from .use_cases import (
    ResetStuckFiles,
    DequeueNextFile,
    GetQueueStats,
    SyncFilesystemSnapshot,
)
from .services import FileService

__all__ = [
    "ResetStuckFiles",
    "DequeueNextFile",
    "GetQueueStats",
    "SyncFilesystemSnapshot",
    "FileService",
]
