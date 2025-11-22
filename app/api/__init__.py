"""
API endpoints package
"""

from app.api.documents import router as documents_router
from app.api.search import router as search_router
from app.api.admin import router as admin_router

__all__ = ["documents_router", "search_router", "admin_router"]
