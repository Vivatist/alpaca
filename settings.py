"""
Настройки приложения
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # Application
    APP_NAME: str = "ALPACA RAG"
    VERSION: str = "2.0.0"
    
    # Supabase Database (PostgreSQL с pgvector)
    # Формат: postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
    DATABASE_URL: str
    
    # File Monitoring
    MONITORED_PATH: str = "/home/alpaca/monitored_folder"
    SCAN_INTERVAL: int = 15  # секунды
    
    # Unstructured API
    UNSTRUCTURED_API_URL: str = "http://localhost:9000/general/v0/general"
    
    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_LLM_MODEL: str = "qwen2.5:32b"
    OLLAMA_EMBEDDING_MODEL: str = "bge-m3"
    
    # Prefect
    PREFECT_API_URL: str = "http://localhost:4200/api"
    PREFECT_SERVER_HOST: str = "0.0.0.0"
    PREFECT_SERVER_PORT: int = 4200
    PREFECT_LOGGING_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
