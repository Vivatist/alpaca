"""
Контракты Ingest Service.

Все type aliases и Protocol'ы для компонентов пайплайна.
Изолированы от core/ для полной независимости сервиса.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Protocol, List, Optional, Dict, Any, runtime_checkable
from enum import Enum


@dataclass
class FileSnapshot:
    """Снимок файла для обработки."""
    
    hash: str
    path: str
    size: int = 0
    status_sync: str = "added"
    raw_text: str = ""
    metadata: Optional[Dict[str, Any]] = None
    mtime: Optional[float] = None  # Время модификации файла
    last_checked: Optional[str] = None  # Время последней проверки
    
    @property
    def full_path(self) -> str:
        """Полный путь к файлу на диске."""
        from settings import settings
        return f"{settings.MONITORED_PATH}/{self.path}"


class SyncStatus(str, Enum):
    """Статусы синхронизации файлов."""
    OK = "ok"
    ADDED = "added"
    UPDATED = "updated"
    DELETED = "deleted"
    PROCESSED = "processed"
    ERROR = "error"


# === Component Contracts ===

# Parser: (file) -> raw_text
Parser = Callable[[FileSnapshot], str]

# Cleaner: (text) -> cleaned_text
Cleaner = Callable[[str], str]

# Chunker: (file_with_text) -> list_of_chunks
Chunker = Callable[[FileSnapshot], List[str]]

# Embedder: (repository, file, chunks, metadata) -> count_of_saved_chunks
Embedder = Callable[["Repository", FileSnapshot, List[str], Dict[str, Any]], int]

# MetaExtractor: (file_with_text) -> metadata_dict
MetaExtractor = Callable[[FileSnapshot], Dict[str, Any]]


@runtime_checkable
class Repository(Protocol):
    """Протокол репозитория для работы с БД."""
    
    def mark_as_ok(self, file_hash: str) -> bool:
        """Пометить файл как успешно обработанный."""
        ...
    
    def mark_as_error(self, file_hash: str) -> bool:
        """Пометить файл как ошибочный."""
        ...
    
    def mark_as_processed(self, file_hash: str) -> bool:
        """Пометить файл как находящийся в обработке."""
        ...
    
    def delete_chunks_by_hash(self, file_hash: str) -> int:
        """Удалить все чанки файла по хэшу."""
        ...
    
    def delete_file_by_hash(self, file_hash: str) -> bool:
        """Удалить запись о файле по хэшу."""
        ...
    
    def save_chunk(
        self, 
        content: str, 
        metadata: Dict[str, Any], 
        embedding: Optional[List[float]] = None
    ) -> bool:
        """Сохранить чанк с метаданными и эмбеддингом."""
        ...
    
    def set_raw_text(self, file_hash: str, raw_text: str) -> bool:
        """Сохранить raw_text файла."""
        ...


class ParserRegistry:
    """Реестр парсеров по расширениям файлов."""
    
    def __init__(self, parsers: Dict[tuple, Parser]):
        """
        Args:
            parsers: Словарь {(расширения,): парсер}
                     Например: {('.doc', '.docx'): word_parser}
        """
        self._parsers = parsers
        self._extension_map: Dict[str, Parser] = {}
        
        for extensions, parser in parsers.items():
            for ext in extensions:
                self._extension_map[ext.lower()] = parser
    
    def get_parser(self, file_path: str) -> Optional[Parser]:
        """Получить парсер по расширению файла."""
        import os
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        return self._extension_map.get(ext)
    
    def supported_extensions(self) -> List[str]:
        """Список поддерживаемых расширений."""
        return list(self._extension_map.keys())
