"""
Реализации эмбеддеров для создания векторных представлений.

=== НАЗНАЧЕНИЕ ===
Создаёт эмбеддинги (vector[1024]) из текстовых чанков
и сохраняет их в PostgreSQL + pgvector.

=== ЭКСПОРТЫ ===
- custom_embedding — через Ollama bge-m3 (бесплатно, локально)
- langchain_embedding — через LangChain/OpenAI (платно)
- embed_chunks — алиас, по умолчанию custom_embedding

=== СИГНАТУРА ===
    def embedder(repo: FileRepository, file: FileSnapshot, chunks: List[str]) -> int

Возвращает: количество сохранённых чанков

=== ИСПОЛЬЗОВАНИЕ ===

    from core.application.document_processing.embedding import (
        embed_chunks, custom_embedding, langchain_embedding
    )
    from core.domain.files import FileSnapshot

    file = FileSnapshot(path="doc.txt", hash="abc123")
    chunks = ["First chunk...", "Second chunk..."]

    # Использовать дефолтный embedder (Ollama)
    count = embed_chunks(repository, file, chunks)
    print(f"Saved {count} chunks with embeddings")

    # Или явно выбрать embedder
    count = langchain_embedding(repository, file, chunks)

=== КОНФИГУРАЦИЯ ===
Ollama настройки в settings.py:
- OLLAMA_BASE_URL = "http://localhost:11434"
- OLLAMA_EMBEDDING_MODEL = "bge-m3"

Переключение: EMBEDDER_BACKEND="langchain" в .env
"""

from .custom_embedder import custom_embedding
from .langchain_embedder import langchain_embedding

embed_chunks = custom_embedding

__all__ = ["custom_embedding", "langchain_embedding", "embed_chunks"]