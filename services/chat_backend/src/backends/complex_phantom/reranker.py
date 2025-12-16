"""
Комбинированный реранкер для Complex Agent.

Учитывает:
1. base_score (similarity от vector search)
2. freshness (свежесть документа по modified_at)
3. category_boost (приоритет категории документа)

Итоговый score = weighted sum всех факторов.
"""
from datetime import datetime
from typing import List, Optional

from logging_config import get_logger
from .schemas import SearchHit, SearchResult
from .config import (
    RERANK_SIMILARITY_WEIGHT,
    RERANK_FRESHNESS_WEIGHT,
    RERANK_CATEGORY_WEIGHT,
    CATEGORY_PRIORITY,
    MAX_DOCUMENT_AGE_DAYS,
)

logger = get_logger("chat_backend.complex_agent.reranker")


def rerank_results(
    hits: List[SearchHit],
    top_k: Optional[int] = None
) -> List[SearchResult]:
    """
    Реранкинг результатов поиска.
    
    Формула:
        final_score = (
            SIMILARITY_WEIGHT * normalized_base_score +
            FRESHNESS_WEIGHT * freshness_score +
            CATEGORY_WEIGHT * category_boost
        )
    
    Args:
        hits: Список SearchHit из поиска
        top_k: Ограничение на количество результатов (None = все)
        
    Returns:
        Список SearchResult, отсортированный по final_score (убывание)
    """
    if not hits:
        return []
    
    # 1. Нормализуем base_score (0-1)
    max_score = max(h.base_score for h in hits) or 1.0
    min_score = min(h.base_score for h in hits)
    score_range = max_score - min_score if max_score != min_score else 1.0
    
    # 2. Текущая дата для расчёта freshness
    now = datetime.now()
    
    results = []
    for hit in hits:
        # Normalized similarity (0-1)
        normalized_similarity = (hit.base_score - min_score) / score_range if score_range > 0 else 1.0
        
        # Freshness score (0-1)
        freshness = _calculate_freshness(hit.metadata.modified_at, now)
        
        # Category boost (0-1)
        category_boost = _calculate_category_boost(hit.metadata.category)
        
        # Final score
        final_score = (
            RERANK_SIMILARITY_WEIGHT * normalized_similarity +
            RERANK_FRESHNESS_WEIGHT * freshness +
            RERANK_CATEGORY_WEIGHT * category_boost
        )
        
        results.append(SearchResult.from_hit(hit, final_score))
    
    # Сортируем по final_score (убывание)
    results.sort(key=lambda r: r.final_score, reverse=True)
    
    # Ограничиваем top_k
    if top_k is not None:
        results = results[:top_k]
    
    logger.debug(f"Reranked {len(hits)} hits → {len(results)} results")
    return results


def _calculate_freshness(modified_at: Optional[str], now: datetime) -> float:
    """
    Вычислить score свежести документа (0-1).
    
    Чем новее документ, тем выше score:
    - Сегодня = 1.0
    - MAX_DOCUMENT_AGE_DAYS назад = 0.0
    - Старше = 0.0
    
    Args:
        modified_at: Дата в формате ISO 8601
        now: Текущая дата
        
    Returns:
        Freshness score (0-1)
    """
    if not modified_at:
        return 0.0
    
    try:
        # Парсим дату
        if "T" in modified_at:
            doc_date = datetime.fromisoformat(modified_at.replace("Z", "+00:00").split("+")[0])
        else:
            doc_date = datetime.fromisoformat(modified_at)
        
        # Возраст документа в днях
        age_days = (now - doc_date).days
        
        if age_days < 0:
            # Документ из "будущего" — максимальный score
            return 1.0
        
        if age_days >= MAX_DOCUMENT_AGE_DAYS:
            return 0.0
        
        # Линейная интерполяция: 0 дней = 1.0, MAX_DAYS = 0.0
        return 1.0 - (age_days / MAX_DOCUMENT_AGE_DAYS)
        
    except (ValueError, TypeError) as e:
        logger.debug(f"Failed to parse date '{modified_at}': {e}")
        return 0.0


def _calculate_category_boost(category: Optional[str]) -> float:
    """
    Получить boost для категории документа.
    
    Args:
        category: Категория документа
        
    Returns:
        Category boost (0-1) из CATEGORY_PRIORITY
    """
    if not category:
        return 0.3  # Default для документов без категории
    
    return CATEGORY_PRIORITY.get(category, 0.3)
