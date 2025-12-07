#!/usr/bin/env python3
"""
Base Parser для RAG системы ALPACA

Базовый класс для всех парсеров документов с общей функциональностью.
"""

from typing import Optional, TYPE_CHECKING
from abc import ABC, abstractmethod

from logging_config import get_logger

if TYPE_CHECKING:
    from contracts import FileSnapshot


class BaseParser(ABC):
    """Базовый класс. Реализует шаблон Template Method для парсинга."""

    def __init__(self, parser_name: str):
        self.logger = get_logger(f"ingest.parser.{parser_name}")

    def parse(self, file: 'FileSnapshot') -> str:
        """Финальный метод: вызывает реализацию `_parse` и гарантирует непустой текст."""
        text = self._parse(file)
        return self._ensure_text(text, file)

    @abstractmethod
    def _parse(self, file: 'FileSnapshot') -> str:
        """Реализация парсинга в наследнике."""
        raise NotImplementedError

    def _ensure_text(self, text: Optional[str], file: 'FileSnapshot') -> str:
        """Валидация результата парсинга — запрещены пустые строки."""
        if text is None:
            raise ValueError(
                f"Parser {self.__class__.__name__} returned None | file={getattr(file, 'path', 'unknown')}"
            )
        if not text.strip():
            raise ValueError(
                f"Parser {self.__class__.__name__} returned empty text | file={getattr(file, 'path', 'unknown')}"
            )
        return text
