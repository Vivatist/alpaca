"""
None Reranker — без реранкинга (pass-through).

Используется когда реранкинг отключён (RERANKER_TYPE=none).
"""
from typing import List

from logging_config import get_logger

from .protocol import Reranker, RerankItem, RerankResult

logger = get_logger("chat_backend.simple.reranker.none")


class NoneReranker(Reranker):
    """
    Пустой реранкер — просто передаёт результаты без изменений.
    
    rerank_score = similarity (без изменений)
    """
    
    def __init__(self):
        logger.info("✅ NoneReranker initialized (pass-through)")
    
    @property
    def name(self) -> str:
        return "none"
    
    def rerank(
        self, 
        query: str, 
        items: List[RerankItem],
        top_k: int | None = None
    ) -> List[RerankResult]:
        """Передать результаты без изменений."""
        results = [
            RerankResult(
                content=item.content,
                metadata=item.metadata,
                similarity=item.similarity,
                rerank_score=item.similarity  # Без изменений
            )
            for item in items
        ]
        
        if top_k is not None:
            results = results[:top_k]
        
        return results
