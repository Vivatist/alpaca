"""
Simple Chat Backend — RAG через Pipeline + Ollama.

Включает:
- SimpleChatBackend — бэкенд с контекстом в промпте
- Все зависимости: embedder, searcher, pipeline
"""
from .backend import SimpleChatBackend

__all__ = ["SimpleChatBackend"]
