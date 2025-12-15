"""
Настройки MCP Server.

Все настройки загружаются из переменных окружения.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки MCP сервера."""
    
    # Database (через Docker network: supabase-db:5432)
    DATABASE_URL: str = "postgresql://postgres:postgres@supabase-db:5432/postgres"
    
    # Ollama
    OLLAMA_BASE_URL: str = "http://ollama:11434"
    OLLAMA_EMBEDDING_MODEL: str = "bge-m3"
    
    # RAG параметры
    RAG_TOP_K: int = 5
    RAG_SIMILARITY_THRESHOLD: float = 0.3
    
    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
