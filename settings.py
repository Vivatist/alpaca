"""
Настройки приложения

"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Определяем путь к корню проекта (где находится settings.py)
PROJECT_ROOT = Path(__file__).parent
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Настройки приложения
    
    Примечание: Значения можно переопределить через переменные окружения,
    но основные настройки должны быть здесь с разумными значениями по умолчанию.
    """
    
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    # Application
    APP_NAME: str = "ALPACA RAG"
    VERSION: str = "2.0.0"
    ENVIRONMENT: str = "development"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(name)s - %(message)s"
    
    # Supabase Database (PostgreSQL с pgvector)
    # ВАЖНО: DATABASE_URL содержит credentials и должен быть в .env
    DATABASE_URL: str
    
    # File Monitoring
    MONITORED_PATH: str = "/home/alpaca/monitored_folder"
    SCAN_INTERVAL_SECONDS: int = 10  # Интервал сканирования папки
    FILES_TABLE_NAME: str = "files"  # Имя таблицы в БД
    ALLOWED_EXTENSIONS: str = ".docx,.pdf,.txt"  # Разрешённые расширения файлов
    FILE_MIN_SIZE: int = 100  # Минимальный размер файла (bytes)
    FILE_MAX_SIZE: int = 10485760  # Максимальный размер файла (10MB)
    EXCLUDED_DIRS: str = "TMP"  # Исключённые директории (через запятую)
    EXCLUDED_PATTERNS: str = "~*,.*"  # Исключённые паттерны файлов (через запятую)
    
    # File Status Processor
    PROCESS_FILE_CHANGES_INTERVAL: int = 7  # секунды
    MAX_HEAVY_WORKFLOWS: int = 2  # Максимум одновременных тяжёлых воркфлоу
    
    # Unstructured API
    UNSTRUCTURED_API_URL: str = "http://localhost:9000/general/v0/general"
    
    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_LLM_MODEL: str = "qwen2.5:32b"
    OLLAMA_EMBEDDING_MODEL: str = "bge-m3"
    
    # Worker Settings
    WORKER_POLL_INTERVAL: int = 5  # Интервал опроса очереди (секунды)
    WORKER_MAX_CONCURRENT_FILES: int = 5  # Максимум файлов обрабатываемых параллельно
    WORKER_MAX_CONCURRENT_PARSING: int = 2  # Максимум операций парсинга одновременно
    WORKER_MAX_CONCURRENT_EMBEDDING: int = 3  # Максимум операций эмбеддинга одновременно
    WORKER_MAX_CONCURRENT_LLM: int = 2  # Максимум LLM-запросов одновременно
    
    # Testing
    RUN_TESTS_ON_START: bool = True  # Запускать ли тесты при старте приложения
    TEST_SUITE: str = "all"  # "unit", "integration", "all"


settings = Settings()
