"""
Контракты Chat Backend Service.

Type aliases и Protocol'ы для компонентов.
Изолированы от других сервисов для полной независимости.
"""

from __future__ import annotations
from typing import Callable, Protocol, List, Dict, Any, runtime_checkable


# === Component Contracts ===

# Embedder: (text) -> embedding_vector
Embedder = Callable[[str], List[float]]


@runtime_checkable
class Repository(Protocol):
    """Протокол репозитория для работы с БД."""
    
    def search_similar_chunks(
        self,
        embedding: List[float],
        limit: int = 5,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Поиск похожих чанков по embedding."""
        ...
    
    def get_total_chunks_count(self) -> int:
        """Получить общее количество чанков."""
        ...
    
    def get_unique_files_count(self) -> int:
        """Получить количество уникальных файлов."""
        ...


__all__ = [
    "Embedder",
    "Repository",
]
