"""
Доменный тип для чанкеров (Chunker).

=== НАЗНАЧЕНИЕ ===
Определяет контракт для функций, разбивающих распарсенный текст
документа (raw_text) на чанки для последующего эмбеддинга.

=== СИГНАТУРА ===
    Chunker = Callable[[FileSnapshot], List[str]]

Принимает: FileSnapshot с заполненным raw_text
Возвращает: список текстовых чанков

=== ИСПОЛЬЗОВАНИЕ ===

    from core.domain.document_processing.chunkers import Chunker
    from core.domain.files import FileSnapshot

    # Типизация чанкера
    def my_chunker(file: FileSnapshot) -> list[str]:
        if not file.raw_text:
            return []
        # Разбить по 1000 символов
        text = file.raw_text
        return [text[i:i+1000] for i in range(0, len(text), 1000)]

    # Использовать в use-case
    chunker: Chunker = my_chunker
    chunks = chunker(file)

=== РЕАЛИЗАЦИИ ===
См. core/application/document_processing/chunking/custom_chunker.py
"""

from typing import Callable, List
from core.domain.files.models import FileSnapshot

Chunker = Callable[[FileSnapshot], List[str]]

__all__ = ["Chunker"]
