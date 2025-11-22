"""
Pydantic модели для валидации данных
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class FileState(BaseModel):
    """Модель file_state таблицы"""
    id: Optional[int] = None
    file_path: str
    file_size: int
    file_hash: Optional[str] = None
    file_mtime: Optional[float] = None
    status_sync: str = 'ok'
    last_checked: Optional[datetime] = None


class Document(BaseModel):
    """Модель documents таблицы"""
    id: Optional[int] = None
    file_hash: str
    file_path: str
    chunk_index: int
    chunk_text: str
    embedding: Optional[List[float]] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None


class SearchResult(BaseModel):
    """Результат векторного поиска"""
    id: int
    file_hash: str
    file_path: str
    chunk_index: int
    chunk_text: str
    similarity: float
    metadata: Optional[Dict[str, Any]] = None


class RAGResponse(BaseModel):
    """Ответ RAG системы"""
    success: bool
    question: str
    answer: Optional[str] = None
    sources: List[Dict[str, Any]] = []
    num_sources: int = 0
    error: Optional[str] = None


class ParseResponse(BaseModel):
    """Ответ парсера документов"""
    success: bool
    content: Optional[str] = None
    error: Optional[str] = None
    file_path: str
    format: str = 'text'


class FileStats(BaseModel):
    """Статистика файлов"""
    total_files: int
    by_status: Dict[str, int]
    disk_files: int
    db_files: int


class ProcessingStats(BaseModel):
    """Статистика обработки"""
    added: int = 0
    updated: int = 0
    unchanged: int = 0
    deleted: int = 0
    processed: int = 0
    errors: int = 0
