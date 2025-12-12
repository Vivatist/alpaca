"""
ProcessFileEvent - обработка событий от FileWatcher.

Роутинг по статусу файла:
- added: полный пайплайн обработки
- updated: удаление старых чанков + полный пайплайн
- deleted: удаление файла и чанков
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any

from logging_config import get_logger, set_file_marker, clear_file_marker
from contracts import FileSnapshot, Repository
from pipeline.ingest import IngestDocument


@dataclass
class ProcessFileEvent:
    """Use-case для обработки событий FileWatcher."""
    
    ingest_document: IngestDocument
    repository: Repository
    logger_name: str = field(default="ingest.process")
    
    def __post_init__(self):
        self.logger = get_logger(self.logger_name)
    
    def __call__(self, file_info: Dict[str, Any]) -> bool:
        """
        Обработка события о файле.
        
        Args:
            file_info: Словарь с данными файла от FileWatcher
            
        Returns:
            True если обработка успешна
        """
        file = FileSnapshot(**file_info)
        
        # Устанавливаем маркер в самом начале обработки файла
        marker = set_file_marker()
        
        # Полный путь только здесь - дальше идентификация по маркеру
        self.logger.info(f"Start | path={file.path} status={file.status_sync}")
        
        try:
            if file.status_sync == "deleted":
                # Удаляем чанки и запись о файле
                deleted_chunks = self.repository.delete_chunks_by_hash(file.hash)
                self.repository.delete_file_by_hash(file.hash)
                self.logger.info(f"Deleted | chunks={deleted_chunks}")
                return True
            
            if file.status_sync == "updated":
                # Удаляем старые чанки перед переобработкой
                deleted = self.repository.delete_chunks_by_hash(file.hash)
                self.logger.info(f"Deleted old chunks | count={deleted}")
                return self.ingest_document(file)
            
            if file.status_sync == "added":
                # Полный пайплайн
                return self.ingest_document(file)
            
            self.logger.warning(f"Unknown status | status={file.status_sync}")
            return False
            
        except Exception as exc:
            self.logger.error(f"Error | error={exc}")
            self.repository.mark_as_error(file.hash)
            return False
            
        finally:
            # Очищаем маркер в конце обработки
            clear_file_marker()
