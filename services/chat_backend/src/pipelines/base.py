"""
Базовый класс для RAG Pipeline.

Определяет интерфейс, который должны реализовать все пайплайны.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class RAGContext:
    """Контекст для RAG генерации."""
    chunks: List[Dict[str, Any]]  # Найденные чанки
    prompt: str                    # Готовый промпт для LLM
    conversation_id: str           # ID разговора
    system_prompt: str             # Системный промпт


class BasePipeline(ABC):
    """
    Абстрактный базовый класс для RAG pipeline.
    
    Pipeline отвечает за RAG логику: поиск чанков + формирование промпта.
    LLM вызов (sync/stream) делается в API слое.
    """
    
    @abstractmethod
    def prepare_context(
        self,
        query: str,
        conversation_id: Optional[str] = None,
        **kwargs
    ) -> RAGContext:
        """
        Подготавливает контекст для генерации ответа.
        
        Выполняет поиск релевантных чанков, формирует промпт,
        генерирует conversation_id если не передан.
        
        Args:
            query: Вопрос пользователя
            conversation_id: ID разговора (опционально)
            **kwargs: Дополнительные параметры
            
        Returns:
            RAGContext с чанками, промптом и conversation_id
        """
        pass
    
    @abstractmethod
    def build_prompt(self, query: str, chunks: List[Dict[str, Any]]) -> str:
        """
        Формирует prompt для LLM с контекстом.
        
        Args:
            query: Вопрос пользователя
            chunks: Релевантные чанки
            
        Returns:
            Готовый prompt для LLM
        """
        pass


__all__ = ["BasePipeline", "RAGContext"]
