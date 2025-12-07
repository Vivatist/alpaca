"""
API роуты Chat Backend.
"""
from fastapi import APIRouter

from .chat import router as chat_router
from .health import router as health_router
from .files import router as files_router

router = APIRouter()
router.include_router(health_router)
router.include_router(chat_router, prefix="/api")
router.include_router(files_router, prefix="/api")

__all__ = ["router"]
