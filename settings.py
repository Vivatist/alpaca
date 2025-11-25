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
    """Настройки приложения"""
    
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
    DATABASE_URL: str
    
    # File Monitoring (используется парсерами для построения полного пути)
    MONITORED_PATH: str = "/home/alpaca/monitored_folder"
    
    # File Status Processor
    PROCESS_FILE_CHANGES_INTERVAL: int = 7  # секунды
    MAX_HEAVY_WORKFLOWS: int = 2  # Максимум одновременных тяжёлых воркфлоу
    
    # Unstructured API
    UNSTRUCTURED_API_URL: str = "http://localhost:9000/general/v0/general"
    
    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_LLM_MODEL: str = "qwen2.5:32b"
    OLLAMA_EMBEDDING_MODEL: str = "bge-m3"


settings = Settings()
