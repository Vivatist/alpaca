"""
Health check endpoint.
"""
from fastapi import APIRouter

from settings import settings

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": settings.APP_NAME}
