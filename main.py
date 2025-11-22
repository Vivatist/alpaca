"""
ALPACA RAG - Единая точка входа
"""
import os
import warnings

# Подавляем предупреждения pydantic-settings о неиспользуемых ключах конфигурации
os.environ.setdefault("PYTHONWARNINGS", "ignore::UserWarning")
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic_settings.main")

import asyncio
from prefect import flow, task
from app.utils.logging import get_logger
from settings import settings

logger = get_logger(__name__)


@task(name="health_check", log_prints=True)
def health_check():
    """Проверка работоспособности системы"""
    logger.info(f"🚀 {settings.APP_NAME} v{settings.VERSION}")
    logger.info(f"📁 Monitored folder: {settings.MONITORED_PATH}")
    logger.info(f"🤖 LLM Model: {settings.OLLAMA_LLM_MODEL}")
    logger.info(f"🔢 Embedding Model: {settings.OLLAMA_EMBEDDING_MODEL}")
    return True


@flow(name="alpaca_main", log_prints=True)
def main_flow():
    """Основной flow приложения"""
    logger.info("Starting ALPACA RAG system...")
    
    # Проверка здоровья системы
    health_check()
    
    logger.info("ALPACA RAG system initialized successfully")


if __name__ == "__main__":
    try:
        main_flow()
    except KeyboardInterrupt:
        logger.info("Shutting down ALPACA RAG system...")
    except Exception as e:
        logger.error(f"Error in main flow: {e}", exc_info=True)
        raise
