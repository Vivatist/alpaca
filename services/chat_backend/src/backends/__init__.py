"""
Chat Backends Registry.

Паттерн Registry для переключения между реализациями чата:
- simple: RAG через Pipeline + Ollama (по умолчанию)
- agent: LangChain Agent + MCP Server

Переключение через ENV: CHAT_BACKEND=simple|agent

Структура:
- backends/simple/ — все зависимости Simple RAG
- backends/agent/ — все зависимости Agent + MCP

Добавление нового бэкенда:
1. Создать папку backends/mybackend/ с __init__.py и backend.py
2. Экспортировать класс MyBackend из __init__.py
3. Зарегистрировать в BACKENDS
4. Добавить в docker-compose.yml
"""
from typing import Dict, Type, Optional

from logging_config import get_logger
from settings import settings

from .protocol import ChatBackend, StreamEvent, SourceInfo
from .simple import SimpleChatBackend
from .agent import AgentChatBackend

logger = get_logger("chat_backend.backends")


# === Registry ===

BACKENDS: Dict[str, Type[ChatBackend]] = {
    "simple": SimpleChatBackend,
    "agent": AgentChatBackend,
}


def get_backend(backend_type: Optional[str] = None) -> ChatBackend:
    """
    Получить экземпляр бэкенда.
    
    Args:
        backend_type: Тип бэкенда (simple, agent). 
                      Если не указан — берётся из settings.CHAT_BACKEND
                      
    Returns:
        Экземпляр ChatBackend
        
    Raises:
        ValueError: Если бэкенд не найден
    """
    backend_name = backend_type or settings.CHAT_BACKEND
    
    if backend_name not in BACKENDS:
        available = ", ".join(BACKENDS.keys())
        logger.warning(f"Unknown backend '{backend_name}', falling back to 'simple'. Available: {available}")
        backend_name = "simple"
    
    logger.info(f"Using chat backend: {backend_name}")
    return BACKENDS[backend_name]()


# Singleton instance (lazy)
_backend_instance: Optional[ChatBackend] = None


def get_default_backend() -> ChatBackend:
    """
    Получить singleton бэкенда по умолчанию.
    
    Бэкенд создаётся один раз на основе settings.CHAT_BACKEND.
    """
    global _backend_instance
    if _backend_instance is None:
        _backend_instance = get_backend()
    return _backend_instance


def reset_backend():
    """Сбросить singleton (для тестов)."""
    global _backend_instance
    _backend_instance = None


__all__ = [
    # Protocol
    "ChatBackend",
    "StreamEvent",
    "SourceInfo",
    # Implementations
    "SimpleChatBackend",
    "AgentChatBackend",
    # Registry
    "BACKENDS",
    "get_backend",
    "get_default_backend",
    "reset_backend",
]
