"""
API роуты Chat Backend.

Структура эндпоинтов:
- /health — проверка здоровья
- /api/chat — чат с RAG
- /api/backends — список бэкендов  
- /api/files — работа с файлами
"""
from fastapi import APIRouter

from .chat import router as chat_router
from .health import router as health_router
from .files import router as files_router
from .backends import router as backends_router

router = APIRouter()
router.include_router(health_router)
router.include_router(chat_router, prefix="/api")
router.include_router(backends_router, prefix="/api")
router.include_router(files_router, prefix="/api")

__all__ = ["router"]
