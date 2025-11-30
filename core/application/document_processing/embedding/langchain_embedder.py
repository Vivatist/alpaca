"""Минимальная интеграция LangChain для генерации эмбеддингов."""
from __future__ import annotations

from typing import List, Optional, Protocol

import psycopg2
import psycopg2.extras

from core.domain.files.models import FileSnapshot
from core.domain.files.repository import Database
from settings import settings
from utils.logging import get_logger

logger = get_logger("core.embedder.langchain")


class EmbeddingsProvider(Protocol):
    """Минимальный протокол провайдера эмбеддингов LangChain."""

    def embed_documents(self, texts: List[str]) -> List[List[float]]:  # pragma: no cover - типовой контракт
        ...


try:  # pragma: no cover - импорт зависит от опционального пакета
    from langchain_community.embeddings import OllamaEmbeddings
except Exception:  # noqa: BLE001 - важно поймать любые сбои импорта
    OllamaEmbeddings = None  # type: ignore[assignment]


def _build_default_provider() -> Optional[EmbeddingsProvider]:
    """Создаёт провайдер эмбеддингов LangChain, если зависимости доступны."""

    if OllamaEmbeddings is None:
        logger.warning("LangChain embeddings are unavailable: install langchain-community")
        return None

    return OllamaEmbeddings(
        model=settings.OLLAMA_EMBEDDING_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
    )


def langchain_embedding(
    db: Database,
    file: FileSnapshot,
    chunks: List[str],
    provider: Optional[EmbeddingsProvider] = None,
) -> int:
    """Создание эмбеддингов через LangChain провайдер и запись в БД."""

    if not chunks:
        logger.warning(f"No chunks to embed for {file.path}")
        return 0

    provider = provider or _build_default_provider()
    if provider is None:
        return 0

    try:
        vectors = provider.embed_documents(chunks)
    except Exception as exc:  # noqa: BLE001 - хотим логировать любую ошибку провайдера
        logger.error(f"LangChain provider failed | file={file.path} error={exc}")
        return 0

    if len(vectors) != len(chunks):
        logger.error(
            "LangChain provider returned mismatched vectors | chunks=%s vectors=%s",
            len(chunks),
            len(vectors),
        )
        return 0

    with db.get_connection() as conn:
        with conn.cursor() as cur:
            inserted = 0
            for idx, (chunk_text, vector) in enumerate(zip(chunks, vectors)):
                try:
                    embedding_str = "[" + ",".join(map(str, vector)) + "]"
                    metadata = {
                        "file_hash": file.hash,
                        "file_path": file.path,
                        "chunk_index": idx,
                        "total_chunks": len(chunks),
                    }
                    cur.execute(
                        """
                        INSERT INTO chunks (content, metadata, embedding)
                        VALUES (%s, %s, %s::vector)
                        """,
                        (chunk_text, psycopg2.extras.Json(metadata), embedding_str),
                    )
                    inserted += 1
                except Exception as exc:  # noqa: BLE001
                    logger.error(f"Failed to persist chunk #{idx} | file={file.path} error={exc}")
                    continue
            conn.commit()

    logger.info(
        "LangChain embedded %s/%s chunks | file=%s",
        inserted,
        len(chunks),
        file.path,
    )
    return inserted
