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

    from core.application.document_processing.chunking import chunk_document
    from core.domain.files import FileSnapshot

    file = FileSnapshot(path="doc.txt", hash="abc", raw_text="Длинный текст...")

    # Разбить на чанки
    chunks = chunk_document(file)
    print(f"Created {len(chunks)} chunks")

    # Или с кастомным размером
    from core.application.document_processing.chunking import chunking
    chunks = chunking(file, chunk_size=500)

=== ТЕКУЩАЯ РЕАЛИЗАЦИЯ ===
Fixed-size chunking: разбивает текст на части по N символов.

=== TODO ===
- Семантический чанкинг (по параграфам)
- Чанкинг с перекрытием (overlap)
"""

from .custom_chunker import chunking

chunk_document = chunking

__all__ = ["chunking", "chunk_document"]
