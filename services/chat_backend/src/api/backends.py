"""
Backends API — информация о доступных бэкендах.
"""
from fastapi import APIRouter

from settings import settings

router = APIRouter(prefix="/backends", tags=["Backends"])


@router.get("")
async def list_backends():
    """Список доступных бэкендов."""
    from backends import BACKENDS
    return {
        "default": settings.CHAT_BACKEND,
        "available": list(BACKENDS.keys()),
    }
