#!/usr/bin/env python3
"""
Base Parser для RAG системы ALPACA

Базовый класс для всех парсеров документов с общей функциональностью.
"""

from abc import ABC, abstractmethod
from utils.logging import setup_logging, get_logger

setup_logging()
logger = get_logger("alpaca.parser")


class BaseParser(ABC):
    """
    Абстрактный базовый класс для всех парсеров документов
    
    Определяет общий интерфейс и переиспользуемые методы.
    Управляет добавлением ОБЩИХ метаданных (включая file_hash от file-watcher).
    """
    
    def __init__(self, parser_name: str):
        """
        Args:
            parser_name: Имя парсера для логирования
        """
        self.logger = setup_logging(parser_name)
    
    @abstractmethod
    def parse(self, file) -> str:
        """
        Парсинг документа в Markdown с метаданными
        
        Args:
            file_path: Путь к файлу
            file_hash: Хэш файла от file-watcher (mtime-size)
            
        Returns:
            str: Распарсенный текст документа в Markdown
        """
        pass
    
