"""
LLM модуль — генерация ответов через Ollama.

SimpleChatBackend использует stream() из этого модуля.
AgentChatBackend использует langchain_agent напрямую.
"""
from .ollama import stream

__all__ = ["stream"]
