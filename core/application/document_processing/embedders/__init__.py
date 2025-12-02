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
    def embedder(
        repo: FileRepository,
        file: FileSnapshot,
        chunks: List[str],
        doc_metadata: Dict[str, Any] = None
    ) -> int

Возвращает: количество сохранённых чанков

=== ИСПОЛЬЗОВАНИЕ ===

    from core.application.document_processing.embedders import embed_chunks
    from core.domain.files import FileSnapshot

    file = FileSnapshot(path="doc.txt", hash="abc123")
    chunks = ["First chunk...", "Second chunk..."]
    metadata = {"extension": "txt", "title": "My Doc", "keywords": ["test"]}

    # Использовать дефолтный embedder (Ollama)
    count = embed_chunks(repository, file, chunks, metadata)
    print(f"Saved {count} chunks with embeddings and metadata")

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