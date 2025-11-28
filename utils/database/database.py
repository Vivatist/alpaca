"""
Абстрактный базовый класс для работы с базами данных
Определяет интерфейс для всех реализаций БД
"""
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from main import FileID


class Database(ABC):
    """Абстрактный класс для работы с БД в контексте обработки изменений файлов"""
    
    def __init__(self, database_url: str):
        """
        Args:
            database_url: Database connection string
        """
        if not database_url:
            raise ValueError("database_url is required")
        
        self.connection_string = database_url
    
    @abstractmethod
    @contextmanager
    def get_connection(self):
        """Контекстный менеджер для подключения к БД
        
        Yields:
            connection: Database connection object
        """
        pass
    
    @abstractmethod
    def get_processed_count(self) -> int:
        """Получает количество файлов в статусе 'processed'
        
        Returns:
            int: Количество файлов в обработке
        """
        pass
    
    @abstractmethod
    def get_pending_files(self) -> Dict[str, List['FileID']]:
        """Получает файлы, требующие обработки (status_sync in ['added', 'updated', 'deleted'])
        
        Returns:
            dict: Словарь с файлами по статусам
                {
                    'added': [FileID(hash=..., path=...), ...],
                    'updated': [FileID(hash=..., path=...), ...],
                    'deleted': [FileID(hash=..., path=...), ...]
                }
        """
        pass
    
    @abstractmethod
    def mark_as_processed(self, file_hash: str) -> bool:
        """Помечает файл как обработанный (status_sync = 'processed')
        
        Args:
            file_hash: SHA256 хэш файла
        
        Returns:
            bool: True если обновление успешно
        """
        pass
    
    @abstractmethod
    def mark_as_ok(self, file_hash: str) -> bool:
        """Помечает файл как успешно обработанный (status_sync = 'ok')
        
        Args:
            file_hash: SHA256 хэш файла
        
        Returns:
            bool: True если обновление успешно
        """
        pass
    
    @abstractmethod
    def mark_as_error(self, file_hash: str) -> bool:
        """Помечает файл как ошибочный (status_sync = 'error')
        
        Args:
            file_hash: SHA256 хэш файла
        
        Returns:
            bool: True если обновление успешно
        """
        pass
    
    @abstractmethod
    def delete_file_by_hash(self, file_hash: str) -> bool:
        """Удаляет запись файла из files по хэшу
        
        Args:
            file_hash: SHA256 хэш файла
        
        Returns:
            bool: True если удаление успешно
        """
        pass
    
    @abstractmethod
    def delete_chunks_by_hash(self, file_hash: str) -> int:
        """Удаляет все чанки документа из таблицы chunks по хэшу
        
        Args:
            file_hash: SHA256 хэш файла
        
        Returns:
            int: Количество удалённых чанков
        """
        pass
    
    @abstractmethod
    def delete_chunks_by_path(self, file_path: str) -> int:
        """Удаляет все чанки документа из таблицы chunks по пути файла
        
        Args:
            file_path: Путь к файлу
        
        Returns:
            int: Количество удалённых чанков
        """
        pass
    
    @abstractmethod
    def set_raw_text(self, file_hash: str, raw_text: str) -> bool:
        """Сохраняет распарсенный текст файла в БД
        
        Args:
            file_hash: SHA256 хэш файла
            raw_text: Распарсенный текст документа
        
        Returns:
            bool: True если обновление успешно
        """
        pass
    
    @abstractmethod
    def get_chunks_by_hash(self, file_hash: str) -> List[tuple]:
        """Получает все чанки файла по хэшу
        
        Args:
            file_hash: SHA256 хэш файла
        
        Returns:
            List[tuple]: Список кортежей (content, metadata, embedding)
        """
        pass
    
    @abstractmethod
    def save_chunk(self, content: str, metadata: dict, embedding: List[float] = None) -> bool:
        """Сохраняет чанк в БД
        
        Args:
            content: Текст чанка
            metadata: Метаданные чанка (JSONB)
            embedding: Векторное представление чанка (опционально)
        
        Returns:
            bool: True если сохранение успешно
        """
        pass
    
    @abstractmethod
    def get_chunks_count(self, file_hash: str) -> int:
        """Получает количество чанков файла
        
        Args:
            file_hash: SHA256 хэш файла
        
        Returns:
            int: Количество чанков в БД
        """
        pass
    
