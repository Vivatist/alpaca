"""
Date Reranker — сортировка по дате модификации файла.

Более свежие документы получают более высокий rerank_score.
"""
from datetime import datetime
from typing import List

from logging_config import get_logger

from .protocol import Reranker, RerankItem, RerankResult

logger = get_logger("chat_backend.simple.reranker.date")


class DateReranker(Reranker):
    """
    Реранкер по дате модификации.
    
    Сортирует результаты по полю metadata.modified_at (ISO 8601).
    Более свежие документы идут первыми.
    
    Параметры:
    - weight: Вес даты в итоговом score (0-1). 
              1.0 = только дата, 0.0 = только similarity
    """
    
    def __init__(self, weight: float = 0.5):
        """
        Args:
            weight: Вес даты в итоговом score (0-1).
                   Итоговый score = similarity * (1 - weight) + date_score * weight
        """
        self.weight = max(0.0, min(1.0, weight))
        logger.info(f"✅ DateReranker initialized | weight={self.weight}")
    
    @property
    def name(self) -> str:
        return "date"
    
    def _parse_date(self, date_str: str | None) -> datetime | None:
        """Парсинг даты из строки ISO 8601."""
        if not date_str:
            return None
        try:
            # Поддержка форматов: 2023-04-10T10:37:28 или 2023-04-10
            if "T" in date_str:
                return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return datetime.fromisoformat(date_str)
        except (ValueError, TypeError):
            return None
    
    def _calculate_date_score(
        self, 
        date: datetime | None, 
        min_date: datetime, 
        max_date: datetime
    ) -> float:
        """
        Вычислить нормализованный score даты (0-1).
        
        Самая новая дата = 1.0, самая старая = 0.0
        """
        if date is None:
            return 0.0
        
        if min_date == max_date:
            return 1.0  # Все даты одинаковые
        
        total_span = (max_date - min_date).total_seconds()
        date_offset = (date - min_date).total_seconds()
        
        return date_offset / total_span if total_span > 0 else 1.0
    
    def rerank(
        self, 
        query: str, 
        items: List[RerankItem],
        top_k: int | None = None
    ) -> List[RerankResult]:
        """
        Переранжировать по дате модификации.
        
        Итоговый score = similarity * (1 - weight) + date_score * weight
        """
        if not items:
            return []
        
        # 1. Парсим даты
        parsed_items = []
        for item in items:
            date_str = item.metadata.get("modified_at")
            parsed_date = self._parse_date(date_str)
            parsed_items.append((item, parsed_date))
        
        # 2. Находим min/max даты для нормализации
        valid_dates = [d for _, d in parsed_items if d is not None]
        if valid_dates:
            min_date = min(valid_dates)
            max_date = max(valid_dates)
        else:
            # Нет валидных дат — используем только similarity
            min_date = max_date = datetime.now()
        
        # 3. Вычисляем rerank_score
        results = []
        for item, parsed_date in parsed_items:
            date_score = self._calculate_date_score(parsed_date, min_date, max_date)
            
            # Комбинируем similarity и date_score
            rerank_score = (
                item.similarity * (1 - self.weight) + 
                date_score * self.weight
            )
            
            results.append(RerankResult(
                content=item.content,
                metadata=item.metadata,
                similarity=item.similarity,
                rerank_score=rerank_score
            ))
        
        # 4. Сортируем по rerank_score (убывание)
        results.sort(key=lambda x: x.rerank_score, reverse=True)
        
        # 5. Ограничиваем top_k
        if top_k is not None:
            results = results[:top_k]
        
        logger.debug(
            f"🔄 DateReranker: {len(items)} → {len(results)} items | "
            f"weight={self.weight}"
        )
        
        return results
