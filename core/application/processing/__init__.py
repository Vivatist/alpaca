"""
Use-case'ы для обработки документов.

=== НАЗНАЧЕНИЕ ===
Модуль содержит основные use-case'ы пайплайна обработки:
- IngestDocument — полный пайплайн: парсинг → чанкинг → эмбеддинг
- ProcessFileEvent — обработка событий от FileWatcher

=== ПАЙПЛАЙН ===
    1. FileWatcher обнаруживает файл (added/updated/deleted)
    2. Worker получает файл из очереди
    3. ProcessFileEvent решает, что делать:
       - deleted → удалить чанки
       - updated → удалить старые чанки + IngestDocument
       - added → IngestDocument
    4. IngestDocument: parse → chunk → embed → save

=== ИСПОЛЬЗОВАНИЕ ===

    from core.application.processing import IngestDocument, ProcessFileEvent

    # Создание use-case (обычно через bootstrap)
    ingest = IngestDocument(
        repository=repo,
        parser_registry=registry,
        chunker=chunking,
        embedder=custom_embedding,
        parse_semaphore=Semaphore(2),
        embed_semaphore=Semaphore(3),
    )

    # Обработать файл
    success = ingest(file_snapshot)

    # Обработчик событий
    process_event = ProcessFileEvent(ingest_document=ingest, repository=repo)
    process_event(file_info_dict)  # вызывается worker'ом

=== СЕМАФОРЫ ===
Ограничивают параллельность тяжёлых операций:
- parse_semaphore: макс N параллельных парсингов (CPU-bound)
- embed_semaphore: макс M параллельных запросов к Ollama (GPU)
"""

from .use_cases import IngestDocument, ProcessFileEvent

__all__ = [
    "IngestDocument",
    "ProcessFileEvent",
]
