"""
Конфигурация Ingest Service.

Все настройки берутся из переменных окружения.
"""

import json
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List


class Settings(BaseSettings):
    """Настройки сервиса из ENV."""
    
    # Database
    DATABASE_URL: str = "postgresql://postgres:password@localhost:54322/postgres"
    
    # FileWatcher API
    FILEWATCHER_URL: str = "http://filewatcher:8081"
    
    # Ollama
    OLLAMA_BASE_URL: str = "http://ollama:11434"
    OLLAMA_EMBEDDING_MODEL: str = "bge-m3"
    OLLAMA_LLM_MODEL: str = "qwen2.5:32b"
    
    # Worker
    WORKER_POLL_INTERVAL: int = 5
    WORKER_MAX_CONCURRENT_FILES: int = 5
    WORKER_MAX_CONCURRENT_PARSING: int = 2
    WORKER_MAX_CONCURRENT_EMBEDDING: int = 3
    
    # Paths
    MONITORED_PATH: str = "/monitored_folder"
    TMP_MD_PATH: str = "/tmp_md"
    
    # Features
    ENABLE_CLEANER: bool = True
    ENABLE_METAEXTRACTOR: bool = True
    METAEXTRACTOR_BACKEND: str = "llm"  # "simple" | "llm" | "none"
    LLM_METAEXTRACTOR_PREVIEW_LENGTH: int = 2000
    
    # Chunker
    CHUNKER_BACKEND: str = "smart"  # "simple" | "smart"
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    
    # Cleaner pipeline (порядок важен)
    CLEANER_PIPELINE: List[str] = ["simple", "stamps"]
    
    @field_validator('CLEANER_PIPELINE', mode='before')
    @classmethod
    def parse_cleaner_pipeline(cls, v):
        """Парсинг списка из JSON строки или списка."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                # Пробуем как comma-separated
                return [x.strip() for x in v.split(',') if x.strip()]
        return v
    
    # Unstructured API (для PDF OCR)
    UNSTRUCTURED_API_URL: str = "http://unstructured:8000/general/v0/general"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
