"""
Доменный тип для эмбеддеров (Embedder).

=== НАЗНАЧЕНИЕ ===
Определяет контракт для функций, создающих векторные представления
(эмбеддинги) из текстовых чанков и сохраняющих их в БД.

=== СИГНАТУРА ===
    Embedder = Callable[[FileRepository, FileSnapshot, List[str]], int]

Параметры:
- FileRepository: репозиторий для сохранения чанков с векторами
- FileSnapshot: метаданные файла (hash, path)
- List[str]: список текстовых чанков

Возвращает: количество успешно сохранённых чанков

=== ИСПОЛЬЗОВАНИЕ ===

    from core.domain.document_processing.embedders import Embedder
    from core.domain.files import FileSnapshot, FileRepository

    # Типизация эмбеддера
    def my_embedder(
        repo: FileRepository,
        file: FileSnapshot,
        chunks: list[str]
    ) -> int:
        count = 0
        for idx, chunk in enumerate(chunks):
            embedding = get_embedding(chunk)  # запрос к Ollama
            repo.save_chunk(file.hash, chunk, embedding)
            count += 1
        return count

    # Использовать в use-case
    embedder: Embedder = my_embedder
    saved = embedder(repository, file, chunks)

=== РЕАЛИЗАЦИИ ===
- custom_embedding — через Ollama (bge-m3), бесплатно, локально
- langchain_embedding — через LangChain/OpenAI (платно)

См. core/application/document_processing/embedding/
"""

from __future__ import annotations

from typing import Callable, List

from core.domain.files.models import FileSnapshot
from core.domain.files.repository import FileRepository

Embedder = Callable[[FileRepository, FileSnapshot, List[str]], int]

__all__ = ["Embedder"]
