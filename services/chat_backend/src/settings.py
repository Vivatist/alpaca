"""
Настройки Chat Backend Service.

Все значения ОБЯЗАТЕЛЬНЫ и должны быть переданы через ENV.
Сервис упадёт при старте, если чего-то не хватает.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки сервиса."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    # Application
    APP_NAME: str
    VERSION: str
    ENVIRONMENT: str
    LOG_LEVEL: str
    
    # Database (PostgreSQL + pgvector)
    DATABASE_URL: str
    
    # Ollama
    OLLAMA_BASE_URL: str
    OLLAMA_LLM_MODEL: str
    OLLAMA_EMBEDDING_MODEL: str
    
    # RAG Settings
    RAG_TOP_K: int
    RAG_SIMILARITY_THRESHOLD: float
    
    # Streaming Settings
    STREAM_CHUNK_DELAY: float  # Задержка между чанками в секундах (0 = без задержки)
    
    # Pipeline
    PIPELINE_TYPE: str
    
    # Public URL для генерации ссылок на скачивание
    PUBLIC_URL: str


settings = Settings()
