"""
Pydantic модели для Complex Agent Backend.

Все типы данных для поиска, метаданных и debug info.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field


# === Entity Model ===

class EntityModel(BaseModel):
    """Сущность (человек или компания) в документе."""
    type: Literal["person", "company"]
    name: str
    role: Optional[str] = None


# === Metadata Model ===

class MetadataModel(BaseModel):
    """Метаданные документа (из LLM extractor)."""
    # Идентификация
    file_hash: str = ""
    file_path: str = ""
    chunk_index: int = 0
    total_chunks: int = 0
    
    # Файловые метаданные
    extension: str = ""
    modified_at: Optional[str] = None  # ISO 8601
    
    # Семантические метаданные
    title: Optional[str] = None
    summary: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    category: Optional[str] = None
    entities: List[EntityModel] = Field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MetadataModel":
        """Создать из словаря (из БД)."""
        # Преобразуем entities в EntityModel
        entities = []
        for e in data.get("entities", []):
            if isinstance(e, dict) and "name" in e:
                entities.append(EntityModel(
                    type=e.get("type", "person"),
                    name=e["name"],
                    role=e.get("role")
                ))
        
        return cls(
            file_hash=data.get("file_hash", ""),
            file_path=data.get("file_path", ""),
            chunk_index=data.get("chunk_index", 0),
            total_chunks=data.get("total_chunks", 0),
            extension=data.get("extension", ""),
            modified_at=data.get("modified_at"),
            title=data.get("title"),
            summary=data.get("summary"),
            keywords=data.get("keywords", []),
            category=data.get("category"),
            entities=entities,
        )


# === Search Filter ===

class SearchFilter(BaseModel):
    """Фильтры для поиска документов."""
    category: Optional[str] = None
    company: Optional[str] = None
    person: Optional[str] = None
    keywords: Optional[List[str]] = None
    date_from: Optional[str] = None  # YYYY-MM-DD
    date_to: Optional[str] = None    # YYYY-MM-DD
    
    def to_dict(self) -> Dict[str, Any]:
        """Конвертировать в словарь (без None значений)."""
        result = {}
        if self.category:
            result["category"] = self.category
        if self.company:
            result["company"] = self.company
        if self.person:
            result["person"] = self.person
        if self.keywords:
            result["keywords"] = self.keywords
        if self.date_from:
            result["date_from"] = self.date_from
        if self.date_to:
            result["date_to"] = self.date_to
        return result
    
    def is_empty(self) -> bool:
        """Проверить, пусты ли все фильтры."""
        return not any([
            self.category, self.company, self.person,
            self.keywords, self.date_from, self.date_to
        ])
    
    def copy_without(self, *fields: str) -> "SearchFilter":
        """Создать копию без указанных полей."""
        data = self.model_dump()
        for f in fields:
            if f in data:
                data[f] = None
        return SearchFilter(**data)


# === Search Hit (промежуточный результат) ===

class SearchHit(BaseModel):
    """Результат поиска ДО реранкинга."""
    content: str
    metadata: MetadataModel
    base_score: float = 0.0  # similarity от vector search или 0.5 для structured
    
    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "SearchHit":
        """Создать из строки БД."""
        return cls(
            content=row.get("content", ""),
            metadata=MetadataModel.from_dict(row.get("metadata", {})),
            base_score=row.get("similarity", 0.5),
        )


# === Search Result (финальный результат) ===

class SearchResult(BaseModel):
    """Результат поиска ПОСЛЕ реранкинга."""
    content: str
    metadata: MetadataModel
    base_score: float      # Оригинальный score
    final_score: float     # Score после реранкинга
    
    @classmethod
    def from_hit(cls, hit: SearchHit, final_score: float) -> "SearchResult":
        """Создать из SearchHit после реранкинга."""
        return cls(
            content=hit.content,
            metadata=hit.metadata,
            base_score=hit.base_score,
            final_score=final_score,
        )
    
    def to_source_dict(self) -> Dict[str, Any]:
        """Конвертировать в формат для frontend (sources)."""
        return {
            "file_path": self.metadata.file_path,
            "file_name": self.metadata.file_path.split("/")[-1] if self.metadata.file_path else "",
            "chunk_index": self.metadata.chunk_index,
            "similarity": self.final_score,
            "title": self.metadata.title,
            "summary": self.metadata.summary,
            "category": self.metadata.category,
            "modified_at": self.metadata.modified_at,
        }


# === Retry Debug Info ===

class RetryDebugInfo(BaseModel):
    """Отладочная информация о процессе robust_search."""
    attempts: int = 0
    used_filters_per_attempt: List[Dict[str, Any]] = Field(default_factory=list)
    dropped_filters_per_attempt: List[List[str]] = Field(default_factory=list)
    fallback_used: bool = False
    messages: List[str] = Field(default_factory=list)
    
    def add_attempt(
        self, 
        used_filters: Dict[str, Any], 
        dropped_filters: List[str] = None,
        message: str = ""
    ):
        """Добавить информацию о попытке поиска."""
        self.attempts += 1
        self.used_filters_per_attempt.append(used_filters)
        self.dropped_filters_per_attempt.append(dropped_filters or [])
        if message:
            self.messages.append(message)


# === Agent Answer ===

class AgentAnswer(BaseModel):
    """Финальный ответ агента."""
    final_text: str
    used_documents: List[SearchResult] = Field(default_factory=list)
    debug_info: RetryDebugInfo = Field(default_factory=RetryDebugInfo)


# === Extracted Query Filters ===

class ExtractedFilters(BaseModel):
    """Фильтры, извлечённые из запроса пользователя."""
    category: Optional[str] = None
    company: Optional[str] = None
    person: Optional[str] = None
    keywords: Optional[List[str]] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    
    def to_search_filter(self) -> SearchFilter:
        """Конвертировать в SearchFilter."""
        return SearchFilter(
            category=self.category,
            company=self.company,
            person=self.person,
            keywords=self.keywords,
            date_from=self.date_from,
            date_to=self.date_to,
        )
