"""Централизованная конфигурация ALPACA RAG системы"""

from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Optional


class Settings(BaseSettings):
    """Настройки приложения через переменные окружения"""
    
    # Application
    APP_NAME: str = "ALPACA RAG"
    VERSION: str = "2.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"  # development | production
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4
    RELOAD: bool = False  # Hot reload для разработки
    
    # Database (Supabase PostgreSQL)
    DATABASE_URL: str
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_ECHO: bool = False  # SQL logging
    
    # File Monitoring
    MONITORED_PATH: Path = Path("/monitored_folder")
    ALLOWED_EXTENSIONS: list[str] = [".docx", ".pdf", ".txt", ".xlsx", ".pptx"]
    SCAN_INTERVAL: int = 20  # Секунды между сканированиями
    FILE_MIN_SIZE: int = 500  # Байты
    FILE_MAX_SIZE: int = 5_000_000  # 5MB
    EXCLUDED_DIRS: list[str] = ["TMP", "temp", "cache", "__pycache__"]
    EXCLUDED_PATTERNS: list[str] = ["~*", ".*", "*.tmp", "*.swp"]
    
    # Unstructured API (парсинг документов)
    UNSTRUCTURED_URL: str = "http://localhost:9000"
    UNSTRUCTURED_TIMEOUT: int = 300  # 5 минут
    UNSTRUCTURED_STRATEGY: str = "hi_res"  # hi_res | fast | auto
    
    # Ollama (LLM + Embeddings)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_EMBED_MODEL: str = "bge-m3"
    OLLAMA_LLM_MODEL: str = "qwen2.5:14b"
    OLLAMA_TIMEOUT: int = 120  # 2 минуты
    
    # RAG Settings
    CHUNK_SIZE: int = 1000  # Символов в чанке
    CHUNK_OVERLAP: int = 200  # Перекрытие между чанками
    TOP_K_RESULTS: int = 5  # Топ результатов для RAG
    SIMILARITY_THRESHOLD: float = 0.7  # Порог схожести
    
    # Background Tasks
    MAX_CONCURRENT_PROCESSING: int = 2  # Макс одновременных обработок
    TASK_QUEUE_MAX_SIZE: int = 100
    PROCESSING_BATCH_SIZE: int = 10
    
    # Admin Backend
    ADMIN_API_KEY: Optional[str] = None
    CORS_ORIGINS: list[str] = ["*"]
    
    # Logging
    LOG_LEVEL: str = "INFO"  # DEBUG | INFO | WARNING | ERROR
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
