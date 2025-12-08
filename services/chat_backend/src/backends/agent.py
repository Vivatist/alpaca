"""
Agent Chat Backend — LangChain Agent через MCP.

Агент сам решает когда использовать инструмент поиска документов.
Поиск выполняется через внешний MCP-сервер.
"""
import os
from typing import Iterator

from logging_config import get_logger
from settings import settings

from .protocol import ChatBackend, StreamEvent

logger = get_logger("chat_backend.backends.agent")


# Системный промпт по умолчанию для агента
DEFAULT_AGENT_SYSTEM_PROMPT = """Ты — полезный ассистент компании ALPACA. 
У тебя есть инструмент search_documents для поиска информации в документах компании.

Правила:
1. Если вопрос требует информации из документов — используй search_documents
2. Если вопрос общий или не требует поиска — отвечай напрямую
3. НЕ выдумывай информацию о документах — ищи через инструмент
4. Отвечай на русском языке, кратко и по делу"""


def _check_langchain() -> bool:
    """Проверяет доступность LangChain."""
    try:
        from langchain_ollama import ChatOllama
        from langgraph.prebuilt import create_react_agent
        return True
    except ImportError:
        return False


class AgentChatBackend(ChatBackend):
    """
    Агентский бэкенд: LangChain Agent + MCP Server.
    
    Агент автономно решает когда использовать поиск документов.
    В отличие от SimpleChatBackend, контекст НЕ передаётся напрямую —
    агент вызывает инструмент search_documents при необходимости.
    """
    
    def __init__(self, system_prompt: str | None = None):
        """
        Args:
            system_prompt: Системный промпт для агента (опционально)
        """
        self._system_prompt = system_prompt or DEFAULT_AGENT_SYSTEM_PROMPT
        self._langchain_available = None
    
    @property
    def name(self) -> str:
        return "agent"
    
    def _ensure_langchain(self) -> bool:
        """Lazy check для LangChain."""
        if self._langchain_available is None:
            self._langchain_available = _check_langchain()
            if not self._langchain_available:
                logger.warning("LangChain not available for agent backend")
        return self._langchain_available
    
    def stream(
        self,
        query: str,
        conversation_id: str | None = None,
        base_url: str = ""
    ) -> Iterator[StreamEvent]:
        """
        Потоковая генерация через агента.
        
        События:
        - metadata: пустые sources (агент сам ищет)
        - tool_call: агент вызывает инструмент (опционально)
        - chunk: часть ответа
        - done: завершение
        """
        logger.info(f"📨 Agent stream: {query[:50]}...")
        
        if not self._ensure_langchain():
            yield StreamEvent(type="error", data={"error": "LangChain не установлен"})
            return
        
        try:
            from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
            from llm.langchain_agent import _create_agent, AgentConfig
            
            config = AgentConfig()
            agent = _create_agent(config)
            
            # Формируем сообщения
            messages = []
            if self._system_prompt:
                messages.append(SystemMessage(content=self._system_prompt))
            messages.append(HumanMessage(content=query))
            
            # Отправляем metadata (sources пустые — агент сам найдёт)
            yield StreamEvent(
                type="metadata",
                data={
                    "conversation_id": conversation_id or "",
                    "sources": [],  # Агент сам ищет, sources недоступны заранее
                }
            )
            
            # Стримим ответ агента
            for event in agent.stream({"messages": messages}, stream_mode="messages"):
                if isinstance(event, tuple) and len(event) >= 1:
                    message = event[0]
                    
                    # Пропускаем ToolMessage
                    if isinstance(message, ToolMessage):
                        continue
                    
                    # AIMessage с tool_calls — можно отправить как событие
                    if isinstance(message, AIMessage):
                        if hasattr(message, 'tool_calls') and message.tool_calls:
                            # Опционально: отправляем событие tool_call
                            for tc in message.tool_calls:
                                yield StreamEvent(
                                    type="tool_call",
                                    data={
                                        "name": tc.get("name", ""),
                                        "args": tc.get("args", {}),
                                    }
                                )
                            continue
                        
                        # Финальный ответ — стримим
                        if message.content:
                            yield StreamEvent(type="chunk", data={"content": message.content})
            
            yield StreamEvent(type="done", data={})
            logger.info("Agent stream completed")
            
        except Exception as e:
            logger.error(f"❌ Agent stream error: {e}")
            yield StreamEvent(type="error", data={"error": str(e)})
