"""
Vector Searcher для Simple Backend.

Поиск похожих чанков через pgvector в PostgreSQL.
"""
import time
from dataclasses import dataclass
from typing import List, Dict, Any, Callable, Protocol

from logging_config import get_logger

logger = get_logger("chat_backend.simple.searcher")


class Repository(Protocol):
    """Протокол репозитория для searcher."""
    def search_similar_chunks(
        self,
        embedding: List[float],
        limit: int,
        threshold: float
    ) -> List[Dict[str, Any]]:
        ...


@dataclass
class SearchResult:
    """Результат поиска."""
    content: str
    metadata: Dict[str, Any]
    similarity: float


class VectorSearcher:
    """
    Поисковик по векторной базе pgvector.
    
    Принимает:
    - embedder: функция для генерации эмбеддингов запроса
    - repository: репозиторий с методом search_similar_chunks
    """
    
    def __init__(
        self,
        embedder: Callable[[str], List[float]],
        repository: Repository,
        top_k: int = 5,
        threshold: float = 0.3
    ):
        self.embedder = embedder
        self.repository = repository
        self.top_k = top_k
        self.threshold = threshold
    
    def search(self, query: str) -> List[SearchResult]:
        """
        Поиск релевантных чанков по запросу.
        
        Args:
            query: Текстовый запрос
            
        Returns:
            Список SearchResult, отсортированный по similarity
        """
        start_time = time.perf_counter()
        
        # 1. Генерируем эмбеддинг запроса
        embedding = self.embedder(query)
        embed_time = time.perf_counter() - start_time
        
        if not embedding:
            logger.warning(f"Empty embedding for query: {query[:50]}...")
            return []
        
        # 2. Ищем похожие чанки в БД
        search_start = time.perf_counter()
        raw_results = self.repository.search_similar_chunks(
            embedding=embedding,
            limit=self.top_k,
            threshold=self.threshold
        )
        search_time = time.perf_counter() - search_start
        
        total_time = time.perf_counter() - start_time
        
        # 3. Преобразуем в SearchResult
        results = [
            SearchResult(
                content=r.get("content", ""),
                metadata=r.get("metadata", {}),
                similarity=r.get("similarity", 0)
            )
            for r in raw_results
        ]
        
        logger.info(
            f"🔍 Search: {len(results)} results | "
            f"embed={embed_time:.3f}s search={search_time:.3f}s total={total_time:.3f}s"
        )
        
        return results


def build_searcher(
    embedder: Callable[[str], List[float]],
    repository: Repository,
    top_k: int,
    threshold: float
) -> VectorSearcher:
    """
    Построить searcher из компонентов.
    
    Args:
        embedder: Функция эмбеддинга
        repository: Репозиторий
        top_k: Количество результатов
        threshold: Порог схожести
    """
    logger.info(f"✅ Searcher: pgvector | top_k={top_k} threshold={threshold}")
    return VectorSearcher(
        embedder=embedder,
        repository=repository,
        top_k=top_k,
        threshold=threshold
    )
