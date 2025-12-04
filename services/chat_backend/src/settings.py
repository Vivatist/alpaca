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
    APP_NAME: str = "ALPACA Chat Backend"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    
    # Database (PostgreSQL + pgvector)
    DATABASE_URL: str
    
    # Ollama
    OLLAMA_BASE_URL: str
    OLLAMA_LLM_MODEL: str = "qwen2.5:32b"
    OLLAMA_EMBEDDING_MODEL: str = "bge-m3"
    
    # RAG Settings
    RAG_TOP_K: int = 5  # Количество релевантных чанков
    RAG_SIMILARITY_THRESHOLD: float = 0.3  # Минимальный порог схожести
    
    # Pipeline
    PIPELINE_TYPE: str  # Тип пайплайна: simple, conversational, etc.
    
    # Public URL для генерации ссылок на скачивание
    # Если не задан, используется base_url из запроса
    PUBLIC_URL: str = ""


settings = Settings()
