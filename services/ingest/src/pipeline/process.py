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

from logging_config import get_logger
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
        self.logger.info(f"Processing file | path={file.path} status={file.status_sync}")
        
        try:
            if file.status_sync == "deleted":
                # Удаляем чанки и запись о файле
                deleted_chunks = self.repository.delete_chunks_by_hash(file.hash)
                self.repository.delete_file_by_hash(file.hash)
                self.logger.info(f"🗑️ Deleted file and {deleted_chunks} chunks | path={file.path}")
                return True
            
            if file.status_sync == "updated":
                # Удаляем старые чанки перед переобработкой
                deleted = self.repository.delete_chunks_by_hash(file.hash)
                self.logger.info(f"🪓 Deleted {deleted} old chunks | path={file.path}")
                return self.ingest_document(file)
            
            if file.status_sync == "added":
                # Полный пайплайн
                return self.ingest_document(file)
            
            self.logger.warning(f"Unknown status | status={file.status_sync} path={file.path}")
            return False
            
        except Exception as exc:
            self.logger.error(f"Error processing | path={file.path} error={exc}")
            self.repository.mark_as_error(file.hash)
            return False
