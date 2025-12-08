"""
LangChain Agent RAG - агентский RAG со стримингом.

Использует LangChain для создания агента с инструментами.
Агент сам решает когда использовать поиск документов.

Работает через MCP-сервер (Model Context Protocol) для поиска документов.
MCP_SERVER_URL должен быть указан в настройках или переменных окружения.

Для переключения между обычным RAG и агентским:
1. В settings добавить LLM_BACKEND=langchain_agent
2. Указать MCP_SERVER_URL (по умолчанию http://localhost:8083)
"""

import os
from typing import Optional, Iterator, List, Dict, Any
from dataclasses import dataclass

import httpx

from logging_config import get_logger
from settings import settings

logger = get_logger("chat_backend.llm.langchain_agent")

# Ленивый импорт LangChain (может быть не установлен)
_langchain_available = None


def _check_langchain():
    """Проверяет доступность LangChain и кэширует результат."""
    global _langchain_available
    if _langchain_available is None:
        try:
            from langchain_ollama import ChatOllama
            from langchain_core.messages import HumanMessage, SystemMessage, AIMessageChunk
            from langchain_core.tools import tool
            from langgraph.prebuilt import create_react_agent
            _langchain_available = True
        except ImportError as e:
            logger.warning(f"LangChain not available: {e}")
            _langchain_available = False
    return _langchain_available


@dataclass
class AgentConfig:
    """Конфигурация агента."""
    model: str = None
    base_url: str = None
    temperature: float = 0.7
    max_tokens: int = 2048
    mcp_server_url: str = None  # URL MCP-сервера для поиска
    
    def __post_init__(self):
        self.model = self.model or getattr(settings, 'OLLAMA_LLM_MODEL', 'qwen2.5:32b')
        self.base_url = self.base_url or getattr(settings, 'OLLAMA_BASE_URL', 'http://ollama:11434')
        # MCP-сервер: из settings, ENV или localhost по умолчанию
        self.mcp_server_url = (
            self.mcp_server_url 
            or getattr(settings, 'MCP_SERVER_URL', None)
            or os.getenv('MCP_SERVER_URL', 'http://localhost:8083')
        )


def _search_via_mcp(query: str, mcp_url: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Поиск документов через MCP-сервер.
    
    Args:
        query: Поисковый запрос
        mcp_url: URL MCP-сервера
        top_k: Количество результатов
        
    Returns:
        Список чанков с content, metadata, similarity
    """
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{mcp_url}/tools/search_documents",
                json={"query": query, "top_k": top_k}
            )
            response.raise_for_status()
            data = response.json()
            
            # Преобразуем формат MCP DocumentChunk в внутренний формат
            chunks = []
            for c in data.get("chunks", []):
                chunks.append({
                    "content": c.get("content", ""),
                    "metadata": {
                        "file_path": c.get("file_path", ""),
                        "file_name": c.get("file_name", ""),
                        "title": c.get("title"),
                        "summary": c.get("summary"),
                        "category": c.get("category"),
                        "chunk_index": c.get("chunk_index", 0),
                    },
                    "similarity": c.get("similarity", 0),
                })
            
            logger.debug(f"MCP search '{query[:30]}...' → {len(chunks)} chunks")
            return chunks
            
    except httpx.HTTPStatusError as e:
        logger.error(f"MCP HTTP error: {e.response.status_code} - {e.response.text}")
    except httpx.RequestError as e:
        logger.error(f"MCP request error: {e}")
    except Exception as e:
        logger.error(f"MCP search error: {e}")
    
    return []


def _create_search_tool(config: AgentConfig):
    """Создаёт инструмент поиска для агента через MCP."""
    from langchain_core.tools import tool
    
    @tool
    def search_documents(query: str) -> str:
        """
        Поиск релевантных документов в базе знаний компании.
        Используй этот инструмент когда нужно найти информацию в документах,
        договорах, письмах или другой корпоративной документации.
        
        Args:
            query: Поисковый запрос на естественном языке
            
        Returns:
            Найденные фрагменты документов с метаданными
        """
        if not config.mcp_server_url:
            return "Ошибка: MCP_SERVER_URL не настроен"
        
        chunks = _search_via_mcp(query, config.mcp_server_url, top_k=5)
        
        if not chunks:
            return "Документы по запросу не найдены"
        
        # Форматируем результаты для LLM
        results = []
        for i, chunk in enumerate(chunks, 1):
            metadata = chunk.get("metadata", {})
            file_path = metadata.get("file_path", "неизвестный источник")
            title = metadata.get("title") or metadata.get("file_name") or file_path
            content = chunk.get("content", "")[:500]  # Ограничиваем длину
            similarity = chunk.get("similarity", 0)
            
            result = f"[Документ {i}] {title} (релевантность: {similarity:.2f})\n{content}"
            results.append(result)
        
        logger.info(f"🔍 Agent search: '{query[:30]}...' → {len(results)} results")
        return "\n\n---\n\n".join(results)
    
    return search_documents


def _create_agent(config: AgentConfig):
    """Создаёт LangChain агента с инструментами."""
    from langchain_ollama import ChatOllama
    from langgraph.prebuilt import create_react_agent
    
    # Создаём LLM
    llm = ChatOllama(
        model=config.model,
        base_url=config.base_url,
        temperature=config.temperature,
        num_predict=config.max_tokens,
    )
    
    # Инструменты с доступом к config для MCP
    tools = [_create_search_tool(config)]
    
    # Создаём агента
    agent = create_react_agent(llm, tools)
    
    return agent


def generate_response(
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2048
) -> str:
    """
    Синхронная генерация ответа через LangChain агента.
    
    Агент может использовать инструменты (поиск документов) для ответа.
    """
    if not _check_langchain():
        logger.error("LangChain not available, falling back to empty response")
        return ""
    
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        
        config = AgentConfig(temperature=temperature, max_tokens=max_tokens)
        agent = _create_agent(config)
        
        # Формируем сообщения
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))
        
        # Запускаем агента
        result = agent.invoke({"messages": messages})
        
        # Извлекаем финальный ответ
        final_messages = result.get("messages", [])
        if final_messages:
            return final_messages[-1].content
        
        return ""
        
    except Exception as e:
        logger.error(f"LangChain agent error: {e}")
        return ""


def generate_response_stream(
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2048
) -> Iterator[str]:
    """
    Потоковая генерация ответа через LangChain агента.
    
    Yields:
        Части ответа по мере генерации, включая шаги рассуждения агента
    """
    if not _check_langchain():
        logger.error("LangChain not available")
        yield "Ошибка: LangChain не установлен"
        return
    
    try:
        from langchain_core.messages import HumanMessage, SystemMessage, AIMessageChunk
        
        config = AgentConfig(temperature=temperature, max_tokens=max_tokens)
        agent = _create_agent(config)
        
        # Формируем сообщения
        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))
        
        # Стримим ответ агента
        for event in agent.stream({"messages": messages}, stream_mode="messages"):
            # event это tuple (message, metadata)
            if isinstance(event, tuple) and len(event) >= 1:
                message = event[0]
                
                # AIMessageChunk содержит части ответа
                if hasattr(message, 'content') and message.content:
                    # Пропускаем tool calls, стримим только текст
                    if not hasattr(message, 'tool_calls') or not message.tool_calls:
                        yield message.content
        
        logger.info("LangChain agent stream completed")
        
    except Exception as e:
        logger.error(f"LangChain agent stream error: {e}")
        yield f"Ошибка агента: {e}"


# Для совместимости с интерфейсом
__all__ = [
    "generate_response",
    "generate_response_stream",
    "AgentConfig",
]
