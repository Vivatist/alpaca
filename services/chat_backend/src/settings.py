"""
Настройки Chat Backend Service.

Все значения читаются из ENV переменных (docker-compose.yml).
Значения по умолчанию НЕ ЗАДАЮТСЯ — сервис упадёт, если ENV не установлен.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Настройки сервиса — только чтение ENV.
    
    НЕ добавляйте сюда значения по умолчанию!
    Все настройки задаются в docker-compose.yml.
    """
    
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
    
    # Chat Backend: simple (RAG+Ollama) | agent (LangChain+MCP)
    CHAT_BACKEND: str
    
    # MCP Server URL для agent бэкенда
    MCP_SERVER_URL: str
    
    # RAG Settings
    RAG_TOP_K: int
    RAG_SIMILARITY_THRESHOLD: float
    
    # Reranker: none | date
    RERANKER_TYPE: str
    
    # Streaming Settings
    STREAM_CHUNK_DELAY: float
    
    # Pipeline
    PIPELINE_TYPE: str
    
    # Public URL для генерации ссылок на скачивание
    PUBLIC_URL: str


def get_settings() -> Settings:
    """Получить настройки из ENV."""
    return Settings()


# Синглтон для обратной совместимости
settings = get_settings()
