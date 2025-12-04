"""
Searchers для поиска релевантных документов.

Поддерживает:
- vector: поиск через pgvector по косинусной близости

См. HOW_TO_ADD_SEARCHER.md для инструкции по добавлению нового searcher'а.
"""

from typing import Dict

from logging_config import get_logger
from contracts import Embedder, Repository
from settings import settings

from .vector import VectorSearcher

logger = get_logger("chat_backend.searcher")


# Тип searcher'а
SearcherClass = type[VectorSearcher]

# Реестр доступных searchers
SEARCHERS: Dict[str, SearcherClass] = {
    "vector": VectorSearcher,
}


def build_searcher(embedder: Embedder, repository: Repository) -> VectorSearcher:
    """
    Создаёт searcher на основе настроек.
    
    Args:
        embedder: Функция для эмбеддинга текста
        repository: Репозиторий для поиска чанков
        
    Returns:
        Инстанс searcher'а
    """
    backend = getattr(settings, 'SEARCHER_BACKEND', 'vector')
    
    if backend not in SEARCHERS:
        logger.warning(f"Unknown searcher '{backend}', falling back to vector")
        backend = "vector"
    
    logger.info(f"Using {backend} searcher")
    return SEARCHERS[backend](embedder, repository)


__all__ = [
    "VectorSearcher",
    "SEARCHERS",
    "build_searcher",
]
