"""
API роуты Chat Backend.
"""
from fastapi import APIRouter

from .chat import router as chat_router

router = APIRouter(prefix="/api")
router.include_router(chat_router)

__all__ = ["router"]
