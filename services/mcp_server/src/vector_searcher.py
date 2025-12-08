"""
Vector Searcher для MCP Server — семантический поиск.
"""

from typing import List, Dict, Any

from logging_config import get_logger
from settings import settings

logger = get_logger("mcp_server.vector_searcher")


class VectorSearcher:
    """Семантический поиск по векторной БД."""
    
    def __init__(self, embedder, repository):
        self.embedder = embedder
        self.repository = repository
    
    def search(
        self,
        query: str,
        top_k: int = None,
        threshold: float = None
    ) -> List[Dict[str, Any]]:
        """
        Поиск релевантных документов.
        
        Args:
            query: Поисковый запрос
            top_k: Количество результатов
            threshold: Минимальный порог релевантности
            
        Returns:
            Список чанков с content, metadata, similarity
        """
        top_k = top_k or settings.RAG_TOP_K
        threshold = threshold or settings.RAG_SIMILARITY_THRESHOLD
        
        # Генерируем embedding запроса
        query_embedding = self.embedder.embed(query)
        
        # Ищем похожие чанки
        chunks = self.repository.search_similar(
            embedding=query_embedding,
            top_k=top_k,
            threshold=threshold
        )
        
        logger.debug(f"Search '{query[:30]}...' → {len(chunks)} results")
        return chunks
