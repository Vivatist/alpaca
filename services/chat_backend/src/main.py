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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle: startup и shutdown."""
    setup_logging()
    logger.info(f"🚀 {settings.APP_NAME} v{settings.VERSION} starting...")
    logger.info(f"📡 Ollama: {settings.OLLAMA_BASE_URL}")
    logger.info(f"🗄️ Database: {settings.DATABASE_URL[:50]}...")
    
    # LangChain агент теперь использует MCP-сервер напрямую
    # Никакой инициализации поиска не требуется
    
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
