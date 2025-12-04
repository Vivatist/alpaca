"""
Базовый класс для RAG Pipeline.

Определяет интерфейс, который должны реализовать все пайплайны.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class BasePipeline(ABC):
    """
    Абстрактный базовый класс для RAG pipeline.
    
    Все пайплайны должны реализовать метод generate_answer().
    """
    
    @abstractmethod
    def generate_answer(
        self,
        query: str,
        conversation_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Генерирует ответ на вопрос пользователя.
        
        Args:
            query: Вопрос пользователя
            conversation_id: ID разговора (для истории)
            **kwargs: Дополнительные параметры
            
        Returns:
            Dict с обязательными полями:
            - answer: str — текст ответа
            - conversation_id: str — ID разговора
            - sources: List[Dict] — список источников
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


__all__ = ["BasePipeline"]
