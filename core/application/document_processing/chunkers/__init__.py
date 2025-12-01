"""
Реализации чанкеров для разбиения текста.

=== НАЗНАЧЕНИЕ ===
Разбивает распарсенный текст (raw_text) на чанки для
последующего эмбеддинга и векторного поиска.

=== ЭКСПОРТЫ ===
- chunking — функция разбиения (fixed-size, 1000 символов)
- chunk_document — алиас для удобства

=== СИГНАТУРА ===
    def chunking(file: FileSnapshot, chunk_size: int = 1000) -> List[str]

=== ИСПОЛЬЗОВАНИЕ ===

    from core.application.document_processing.chunkers import chunk_document
    from core.domain.files import FileSnapshot

    file = FileSnapshot(path="doc.txt", hash="abc", raw_text="Длинный текст...")

    # Разбить на чанки
    chunks = chunk_document(file)
    print(f"Created {len(chunks)} chunks")

    # Или с кастомным размером
    from core.application.document_processing.chunkers import chunking
    chunks = chunking(file, chunk_size=500)

=== РЕАЛИЗАЦИИ ===
- simple_chunker: Fixed-size chunking (без overlap)
- smart_chunker: LangChain RecursiveCharacterTextSplitter с overlap

=== ВЫБОР ЧАНКЕРА ===
Выбор осуществляется через settings.CHUNKER_BACKEND:
- "simple" — простой чанкер без перекрытия
- "smart" — умный чанкер с LangChain (по умолчанию)

Дополнительные настройки:
- settings.CHUNK_SIZE — размер чанка (по умолчанию 1000)
- settings.CHUNK_OVERLAP — перекрытие для smart (по умолчанию 200)
"""
from typing import List
from settings import settings
from core.domain.files.models import FileSnapshot

from .simple_chunker import chunking as simple_chunking
from .smart_chunker import smart_chunking


def chunk_document(file: FileSnapshot) -> List[str]:
    """
    Разбивает документ на чанки согласно настройкам.
    
    Использует settings.CHUNKER_BACKEND для выбора реализации:
    - "simple" — простое разбиение по размеру
    - "smart" — умное разбиение с LangChain и overlap
    """
    if settings.CHUNKER_BACKEND == "simple":
        return simple_chunking(file)
    else:  # "smart" или любое другое значение
        return smart_chunking(
            file,
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )


# Алиас для совместимости
chunking = chunk_document

__all__ = ["chunking", "chunk_document", "smart_chunking", "simple_chunking"]
