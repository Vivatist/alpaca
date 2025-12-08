"""
AgentChatBackend — основной класс бэкенда.

LangChain Agent + MCP Server для автономного поиска.
"""
from typing import Iterator

from logging_config import get_logger
from settings import settings

from ..protocol import ChatBackend, StreamEvent
from .mcp import search_via_mcp
from .langchain import check_langchain, create_agent

logger = get_logger("chat_backend.agent")


DEFAULT_SYSTEM_PROMPT = """Ты — полезный ассистент компании ALPACA. 
У тебя есть инструмент search_documents для поиска информации в документах компании.

Правила:
1. Если вопрос требует информации из документов — используй search_documents
2. Если вопрос общий или не требует поиска — отвечай напрямую
3. НЕ выдумывай информацию о документах — ищи через инструмент
4. Отвечай на русском языке, кратко и по делу"""


def _get_mcp_url() -> str:
    """Получить URL MCP-сервера."""
    return getattr(settings, 'MCP_SERVER_URL', 'http://localhost:8083')


class AgentChatBackend(ChatBackend):
    """
    Агентский бэкенд: LangChain Agent + MCP Server.
    
    Агент автономно решает когда использовать поиск документов.
    """
    
    def __init__(self, system_prompt: str | None = None):
        self._system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self._langchain_available = None
    
    @property
    def name(self) -> str:
        return "agent"
    
    def _ensure_langchain(self) -> bool:
        """Lazy check для LangChain."""
        if self._langchain_available is None:
            self._langchain_available = check_langchain()
            if not self._langchain_available:
                logger.warning("LangChain not available")
        return self._langchain_available
    
    def _create_search_func(self):
        """Создать функцию поиска через MCP."""
        mcp_url = _get_mcp_url()
        def search_func(query: str, top_k: int = 5):
            return search_via_mcp(query, top_k=top_k, mcp_url=mcp_url)
        return search_func
    
    def stream(
        self,
        query: str,
        conversation_id: str | None = None,
        base_url: str = ""
    ) -> Iterator[StreamEvent]:
        """Потоковая генерация через агента."""
        logger.info(f"📨 Agent stream: {query[:50]}...")
        
        if not self._ensure_langchain():
            yield StreamEvent(type="error", data={"error": "LangChain не установлен"})
            return
        
        try:
            from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
            
            agent = create_agent(
                base_url=settings.OLLAMA_BASE_URL,
                model=settings.OLLAMA_LLM_MODEL,
                search_func=self._create_search_func()
            )
            
            messages = []
            if self._system_prompt:
                messages.append(SystemMessage(content=self._system_prompt))
            messages.append(HumanMessage(content=query))
            
            # Отправляем metadata (sources пустые — агент сам найдёт)
            yield StreamEvent(
                type="metadata",
                data={"conversation_id": conversation_id or "", "sources": []}
            )
            
            # Стримим ответ агента
            for event in agent.stream({"messages": messages}, stream_mode="messages"):
                if isinstance(event, tuple) and len(event) >= 1:
                    message = event[0]
                    
                    if isinstance(message, ToolMessage):
                        continue
                    
                    if isinstance(message, AIMessage):
                        if hasattr(message, 'tool_calls') and message.tool_calls:
                            for tc in message.tool_calls:
                                yield StreamEvent(
                                    type="tool_call",
                                    data={"name": tc.get("name", ""), "args": tc.get("args", {})}
                                )
                            continue
                        
                        if message.content:
                            yield StreamEvent(type="chunk", data={"content": message.content})
            
            yield StreamEvent(type="done", data={})
            logger.debug("Agent stream completed")
            
        except Exception as e:
            logger.error(f"❌ Agent stream error: {e}")
            yield StreamEvent(type="error", data={"error": str(e)})
