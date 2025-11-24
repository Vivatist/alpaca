"""
Настройки приложения
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
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
    
    # Prefect
    PREFECT_API_URL: str = "http://localhost:4200/api"
    PREFECT_SERVER_HOST: str = "0.0.0.0"
    PREFECT_SERVER_PORT: int = 4200
    PREFECT_LOGGING_LEVEL: str = "INFO"
    


settings = Settings()
