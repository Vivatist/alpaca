"""
Chat Backend Service - REST API для чата с RAG.
"""
from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from settings import settings
from logging_config import setup_logging, get_logger
from api import router as api_router


logger = get_logger("chat_backend")


def _init_agent_search():
    """Регистрирует функцию поиска для LangChain агента."""
    try:
        from llm import get_backend_name
        if get_backend_name() == "langchain_agent":
            from pipelines import get_pipeline
            from llm.langchain_agent import set_search_function
            
            pipeline = get_pipeline()
            set_search_function(pipeline.searcher.search)
            logger.info("✅ Agent search function initialized")
    except Exception as e:
        logger.warning(f"Could not init agent search: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle: startup и shutdown."""
    setup_logging()
    logger.info(f"🚀 {settings.APP_NAME} v{settings.VERSION} starting...")
    logger.info(f"📡 Ollama: {settings.OLLAMA_BASE_URL}")
    logger.info(f"🗄️ Database: {settings.DATABASE_URL[:50]}...")
    
    # Инициализируем поиск для агента
    _init_agent_search()
    
    yield
    logger.info("👋 Chat Backend shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="REST API для чата с RAG-системой ALPACA",
    lifespan=lifespan,
    root_path=os.getenv("ROOT_PATH", ""),
)

# CORS для фронтенда
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В проде ограничить
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Роуты
app.include_router(api_router)
