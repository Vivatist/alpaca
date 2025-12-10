"""
Extension Reranker — приоритизация по расширению файла.

Документы ранжируются по приоритету расширения из заданного списка.
Расширения в начале списка получают более высокий score.
"""
from typing import List

from logging_config import get_logger

from .protocol import Reranker, RerankItem, RerankResult

logger = get_logger("chat_backend.reranker.extension")


class ExtensionReranker(Reranker):
    """
    Реранкер по расширению файла.
    
    Приоритизирует документы по расширению из заданного списка.
    Первое расширение в списке = самый высокий приоритет.
    Расширения не из списка получают минимальный score.
    
    Параметры класса:
    - DEFAULT_TOP_K: 5 (отсечение после реранкинга)
    - DEFAULT_EXTENSIONS: ["pdf", "docx", "doc", "pptx", "ppt"]
    - DEFAULT_WEIGHT: 0.3 (вес расширения в итоговом score)
    """
    
    # Настройки реранкера (изменять здесь, НЕ через ENV)
    DEFAULT_TOP_K = 5
    DEFAULT_EXTENSIONS = ["pdf", "docx", "doc", "pptx", "ppt"]
    DEFAULT_WEIGHT = 0.3  # Вес расширения (0.3 = 30% extension, 70% similarity)
    
    def __init__(
        self, 
        extensions: List[str] | None = None,
        weight: float | None = None,
        top_k: int | None = None
    ):
        """
        Args:
            extensions: Список расширений в порядке приоритета (без точки).
                       Первое = самый высокий приоритет. None = DEFAULT_EXTENSIONS
            weight: Вес расширения в итоговом score (0-1). None = DEFAULT_WEIGHT
            top_k: Максимум результатов. None = DEFAULT_TOP_K
        """
        self.extensions = [e.lower().lstrip('.') for e in (extensions or self.DEFAULT_EXTENSIONS)]
        self.weight = max(0.0, min(1.0, weight if weight is not None else self.DEFAULT_WEIGHT))
        self.top_k = top_k if top_k is not None else self.DEFAULT_TOP_K
        
        logger.info(
            f"✅ ExtensionReranker initialized | "
            f"extensions={self.extensions} weight={self.weight} top_k={self.top_k}"
        )
    
    @property
    def name(self) -> str:
        return "extension"
    
    def _get_extension(self, metadata: dict) -> str:
        """Извлечь расширение из метаданных."""
        # Приоритет: metadata.extension > file_path
        ext = metadata.get("extension", "")
        if not ext:
            file_path = metadata.get("file_path", "")
            if "." in file_path:
                ext = file_path.rsplit(".", 1)[-1]
        return ext.lower().lstrip('.')
    
    def _calculate_extension_score(self, extension: str) -> float:
        """
        Вычислить score расширения (0-1).
        
        Первое расширение в списке = 1.0
        Последнее = 1/len
        Не в списке = 0.0
        """
        if not extension or extension not in self.extensions:
            return 0.0
        
        # Позиция в списке (0 = первый = самый приоритетный)
        position = self.extensions.index(extension)
        n = len(self.extensions)
        
        # Score: первый = 1.0, последний = 1/n
        # Формула: (n - position) / n
        return (n - position) / n
    
    def rerank(
        self, 
        query: str, 
        items: List[RerankItem],
        top_k: int | None = None
    ) -> List[RerankResult]:
        """
        Переранжировать по расширению файла.
        
        Итоговый score = similarity * (1 - weight) + extension_score * weight
        """
        if not items:
            return []
        
        results = []
        for item in items:
            extension = self._get_extension(item.metadata)
            ext_score = self._calculate_extension_score(extension)
            
            # Комбинируем similarity и extension_score
            rerank_score = (
                item.similarity * (1 - self.weight) + 
                ext_score * self.weight
            )
            
            results.append(RerankResult(
                content=item.content,
                metadata=item.metadata,
                similarity=item.similarity,
                rerank_score=rerank_score
            ))
        
        # Сортируем по rerank_score (убывание)
        results.sort(key=lambda x: x.rerank_score, reverse=True)
        
        # Ограничиваем top_k (self.top_k если не передан)
        effective_top_k = top_k if top_k is not None else self.top_k
        if effective_top_k is not None:
            results = results[:effective_top_k]
        
        logger.debug(
            f"🔄 ExtensionReranker: {len(items)} → {len(results)} items | "
            f"weight={self.weight} top_k={effective_top_k}"
        )
        
        return results
