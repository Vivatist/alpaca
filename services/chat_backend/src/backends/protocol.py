"""
Chat Backend Protocol — единый интерфейс для всех реализаций чата.

Все бэкенды (simple, agent, rag_v2 и т.д.) реализуют этот протокол,
что позволяет переключаться между ними без изменения API.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator, Literal, Any


@dataclass
class StreamEvent:
    """
    Унифицированное событие стрима.
    
    Типы событий:
    - metadata: источники, conversation_id (отправляется первым)
    - chunk: часть текстового ответа
    - tool_call: агент вызывает инструмент (опционально)
    - tool_result: результат инструмента (опционально)
    - done: завершение генерации
    - error: ошибка
    """
    type: Literal["metadata", "chunk", "tool_call", "tool_result", "done", "error"]
    data: dict = field(default_factory=dict)


@dataclass
class SourceInfo:
    """Информация об источнике документа."""
    file_path: str
    file_name: str
    chunk_index: int
    similarity: float
    download_url: str
    # Метаданные документа
    title: str | None = None
    summary: str | None = None
    category: str | None = None
    modified_at: str | None = None

    def to_dict(self) -> dict:
        """Конвертация в словарь для JSON."""
        return {
            "file_path": self.file_path,
            "file_name": self.file_name,
            "chunk_index": self.chunk_index,
            "similarity": self.similarity,
            "download_url": self.download_url,
            "title": self.title,
            "summary": self.summary,
            "category": self.category,
            "modified_at": self.modified_at,
        }


@dataclass
class ChatResult:
    """Результат синхронного чата."""
    answer: str
    conversation_id: str
    sources: list[SourceInfo] = field(default_factory=list)


class ChatBackend(ABC):
    """
    Абстрактный бэкенд чата.
    
    Все реализации (simple, agent и т.д.) наследуются от этого класса
    и реализуют методы stream() и chat().
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Уникальное имя бэкенда."""
        ...
    
    @abstractmethod
    def stream(
        self,
        query: str,
        conversation_id: str | None = None,
        base_url: str = ""
    ) -> Iterator[StreamEvent]:
        """
        Потоковая генерация ответа.
        
        Args:
            query: Вопрос пользователя
            conversation_id: ID разговора (опционально)
            base_url: Base URL для формирования ссылок на скачивание
            
        Yields:
            StreamEvent: События стрима (metadata, chunk, done, error)
        """
        ...
    
    @abstractmethod
    def chat(
        self,
        query: str,
        conversation_id: str | None = None,
        base_url: str = ""
    ) -> ChatResult:
        """
        Синхронная генерация ответа.
        
        Args:
            query: Вопрос пользователя
            conversation_id: ID разговора (опционально)
            base_url: Base URL для формирования ссылок на скачивание
            
        Returns:
            ChatResult: Полный ответ с источниками
        """
        ...
