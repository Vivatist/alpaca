"""
Протокол и типы для реранкеров.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class RerankItem:
    """Элемент для реранкинга."""
    content: str
    metadata: Dict[str, Any]
    similarity: float  # Оригинальный score от vector search


@dataclass
class RerankResult:
    """Результат реранкинга."""
    content: str
    metadata: Dict[str, Any]
    similarity: float  # Оригинальный score
    rerank_score: float  # Новый score после реранкинга


class Reranker(ABC):
    """Базовый класс для реранкеров."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Имя реранкера."""
        ...
    
    @abstractmethod
    def rerank(
        self, 
        query: str, 
        items: List[RerankItem],
        top_k: int | None = None
    ) -> List[RerankResult]:
        """
        Переранжировать результаты поиска.
        
        Args:
            query: Запрос пользователя
            items: Список элементов для реранкинга
            top_k: Ограничение количества результатов (None = все)
            
        Returns:
            Отсортированный список RerankResult
        """
        ...
