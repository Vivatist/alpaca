"""
File Status Processor Service - обработка изменений файлов
"""
import requests
from typing import Dict, List, Tuple
from app.utils.logging import get_logger
from .database import Database


logger = get_logger(__name__)


class FileStatusProcessorService:
    """Сервис для обработки изменений статусов файлов"""
    
    def __init__(
        self,
        database_url: str,
        webhook_url: str,
        max_heavy_workflows: int = 2
    ):
        """
        Args:
            database_url: URL подключения к базе данных
            webhook_url: URL webhook для запуска ingestion pipeline
            max_heavy_workflows: Максимум тяжёлых воркфлоу одновременно
        """
        self.db = Database(database_url=database_url)
        self.webhook_url = webhook_url
        self.max_heavy_workflows = max_heavy_workflows
    
    def get_pending_files(self) -> Dict[str, List[Tuple]]:
        """Получение файлов требующих обработки"""
        return self.db.get_pending_files()
    
    def get_processed_count(self) -> int:
        """Получение количества файлов в обработке"""
        return self.db.get_processed_count()
    
    def call_webhook(self, file_path: str, file_hash: str) -> bool:
        """Вызов webhook для ingestion"""
        response = requests.post(self.webhook_url, json={
            'file_path': file_path,
            'file_hash': file_hash,
            'operation': 'process_document'
        }, timeout=5)
        response.raise_for_status()
        return True
    
    def delete_chunks_by_path(self, file_path: str) -> int:
        """Удаление chunks по пути"""
        return self.db.delete_chunks_by_path(file_path)
    
    def delete_chunks_by_hash(self, file_hash: str) -> int:
        """Удаление chunks по хэшу"""
        return self.db.delete_chunks_by_hash(file_hash)
    
    def mark_as_processed(self, file_hash: str) -> bool:
        """Пометка файла как processed"""
        return self.db.mark_as_processed(file_hash)
    
    def mark_as_error(self, file_hash: str) -> bool:
        """Пометка файла как error"""
        return self.db.mark_as_error(file_hash)
    
    def delete_file(self, file_hash: str) -> bool:
        """Удаление записи файла"""
        return self.db.delete_file_by_hash(file_hash)
