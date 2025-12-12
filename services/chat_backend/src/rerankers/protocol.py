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
    
    def to_item(self) -> RerankItem:
        """
        Конвертировать в RerankItem для передачи следующему реранкеру.
        
        rerank_score становится новым similarity, позволяя
        соединять реранкеры в цепочку.
        """
        return RerankItem(
            content=self.content,
            metadata=self.metadata,
            similarity=self.rerank_score  # Передаём rerank_score как новый similarity
        )


def results_to_items(results: List[RerankResult]) -> List[RerankItem]:
    """
    Конвертировать список RerankResult в список RerankItem.
    
    Используется для соединения реранкеров в цепочку:
    
        results1 = reranker1.rerank(query, items)
        results2 = reranker2.rerank(query, results_to_items(results1))
    """
    return [r.to_item() for r in results]


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
