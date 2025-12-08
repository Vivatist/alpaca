"""
Agent Chat Backend — LangChain Agent + MCP Server.

Включает:
- AgentChatBackend — бэкенд с автономным агентом
- MCP интеграция для поиска документов
"""
from .backend import AgentChatBackend

__all__ = ["AgentChatBackend"]
