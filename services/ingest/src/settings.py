"""
Конфигурация Ingest Service.

ВСЕ НАСТРОЙКИ ЗАДАЮТСЯ В docker-compose.yml!
Defaults отсутствуют — приложение упадёт если ENV не задан.
"""

import json
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List


class Settings(BaseSettings):
    """
    Настройки сервиса. ВСЕ ОБЯЗАТЕЛЬНЫ из ENV (docker-compose.yml).
    """
    
    # === CREDENTIALS ===
    DATABASE_URL: str
    
    # === SERVICE URLs ===
    FILEWATCHER_URL: str
    OLLAMA_BASE_URL: str
    UNSTRUCTURED_API_URL: str
    
    # === MODEL SETTINGS ===
    OLLAMA_EMBEDDING_MODEL: str
    OLLAMA_LLM_MODEL: str
    
    # === WORKER SETTINGS ===
    WORKER_POLL_INTERVAL: int
    WORKER_MAX_CONCURRENT_FILES: int
    WORKER_MAX_CONCURRENT_PARSING: int
    WORKER_MAX_CONCURRENT_EMBEDDING: int
    
    # === PATHS ===
    MONITORED_PATH: str
    TMP_MD_PATH: str
    
    # === PIPELINE SETTINGS ===
    ENABLE_CLEANER: bool
    CLEANER_PIPELINE: List[str]
    CHUNKER_BACKEND: str
    CHUNK_SIZE: int
    CHUNK_OVERLAP: int
    ENABLE_METAEXTRACTOR: bool
    METAEXTRACTOR_PIPELINE: List[str]  # ["base", "llm"] - цепочка экстракторов
    LLM_METAEXTRACTOR_PREVIEW_LENGTH: int
    
    # === LOGGING ===
    LOG_LEVEL: str
    
    @field_validator('CLEANER_PIPELINE', 'METAEXTRACTOR_PIPELINE', mode='before')
    @classmethod
    def parse_json_list(cls, v):
        """Парсинг JSON строки в список."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [x.strip() for x in v.split(',') if x.strip()]
        return v
    
    class Config:
        case_sensitive = True


settings = Settings()
