"""
Vector Searcher - поиск релевантных чанков через pgvector.

Использует embedder для получения вектора запроса и repository для поиска.
"""

from typing import List, Dict, Any

from logging_config import get_logger
from settings import settings
from contracts import Embedder, Repository

logger = get_logger("chat_backend.searcher.vector")


class VectorSearcher:
    """Поиск релевантных чанков через векторную близость."""
    
    def __init__(self, embedder: Embedder, repository: Repository):
        """
        Args:
            embedder: Функция для создания эмбеддинга текста
            repository: Репозиторий с методом search_similar_chunks
        """
        self.embedder = embedder
        self.repository = repository
    
    def search(
        self,
        query: str,
        top_k: int = None,
        threshold: float = None
    ) -> List[Dict[str, Any]]:
        """
        Поиск релевантных чанков для запроса.
        
        Args:
            query: Текст запроса
            top_k: Количество результатов (default: из settings.RAG_TOP_K)
            threshold: Минимальный порог схожести (default: из settings.RAG_SIMILARITY_THRESHOLD)
            
        Returns:
            Список чанков с полями: content, metadata, similarity
        """
        if top_k is None:
            top_k = settings.RAG_TOP_K
        if threshold is None:
            threshold = settings.RAG_SIMILARITY_THRESHOLD
        
        # 1. Получаем embedding запроса
        embedding = self.embedder(query)
        
        if not embedding:
            logger.warning("Failed to get embedding for query")
            return []
        
        # 2. Ищем похожие чанки
        chunks = self.repository.search_similar_chunks(
            embedding=embedding,
            limit=top_k,
            threshold=threshold
        )
        
        logger.info(f"🔎 Found {len(chunks)} chunks | query={query[:30]}... threshold={threshold}")
        return chunks


def vector_searcher(embedder: Embedder, repository: Repository, query: str, **kwargs) -> List[Dict[str, Any]]:
    """
    Функциональный интерфейс для поиска.
    
    Args:
        embedder: Функция эмбеддинга
        repository: Репозиторий
        query: Текст запроса
        **kwargs: top_k, threshold
        
    Returns:
        Список релевантных чанков
    """
    searcher = VectorSearcher(embedder, repository)
    return searcher.search(query, **kwargs)
