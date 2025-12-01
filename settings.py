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
    FILES_TABLE_NAME: str = "files"  # Имя таблицы в БД
    
    # File Status Processor (настройки фильтрации файлов находятся в file_watcher Docker-контейнере)
    PROCESS_FILE_CHANGES_INTERVAL: int = 7  # секунды
    MAX_HEAVY_WORKFLOWS: int = 2  # Максимум одновременных тяжёлых воркфлоу
    
    # Unstructured API
    UNSTRUCTURED_API_URL: str = "http://localhost:9000/general/v0/general"
    
    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_LLM_MODEL: str = "qwen2.5:32b"
    OLLAMA_EMBEDDING_MODEL: str = "bge-m3"
    EMBEDDER_BACKEND: str = "custom"  # "custom" или "langchain"
    
    # Cleaner
    ENABLE_CLEANER: bool = True  # Включить очистку текста перед чанкингом
    
    # Chunker
    CHUNKER_BACKEND: str = "smart"  # "simple" или "smart" (LangChain с overlap)
    CHUNK_SIZE: int = 1000  # Размер чанка в символах
    CHUNK_OVERLAP: int = 200  # Перекрытие между чанками (только для smart)
    
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
