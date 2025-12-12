"""
Реранкеры для Chat Backend.

Registry паттерн: выбор реранкера через ENV RERANKER_TYPE.

Использование:
    from rerankers import get_reranker, build_reranker_from_settings
    
    reranker = build_reranker_from_settings()  # Из ENV
    results = reranker.rerank(query, items, top_k=5)
"""
from typing import Type

from logging_config import get_logger

from .protocol import Reranker, RerankItem, RerankResult, results_to_items
from .none import NoneReranker
from .date import DateReranker
from .extension import ExtensionReranker

logger = get_logger("chat_backend.rerankers")


# === Registry ===

RERANKERS: dict[str, Type[Reranker]] = {
    "none": NoneReranker,
    "date": DateReranker,
    "extension": ExtensionReranker,
}


def get_reranker(reranker_type: str, **kwargs) -> Reranker:
    """
    Получить реранкер по типу.
    
    Args:
        reranker_type: Тип реранкера (none, date)
        **kwargs: Параметры для конструктора реранкера
        
    Returns:
        Экземпляр Reranker
        
    Raises:
        ValueError: Если тип реранкера не найден
    """
    if reranker_type not in RERANKERS:
        available = ", ".join(RERANKERS.keys())
        raise ValueError(
            f"Unknown reranker type: {reranker_type}. "
            f"Available: {available}"
        )
    
    reranker_class = RERANKERS[reranker_type]
    reranker = reranker_class(**kwargs)
    
    logger.info(f"✅ Reranker: {reranker.name}")
    return reranker


def build_reranker_from_settings() -> Reranker:
    """
    Построить реранкер из ENV (settings.RERANKER_TYPE).
    
    Настройки берутся ТОЛЬКО из docker-compose.yml через ENV.
    """
    from settings import settings
    
    return get_reranker(settings.RERANKER_TYPE)


# Экспорт
__all__ = [
    "Reranker",
    "RerankItem",
    "RerankResult",
    "results_to_items",
    "NoneReranker",
    "DateReranker",
    "ExtensionReranker",
    "RERANKERS",
    "get_reranker",
    "build_reranker_from_settings",
]
