"""
LangChain Agent RAG - агентский RAG со стримингом.

Использует LangChain для создания агента с инструментами.
Агент сам решает когда использовать поиск документов.

Режимы работы:
1. С внедрённой функцией поиска (set_search_function) - для интеграции с pipeline
2. С MCP-сервером (MCP_SERVER_URL env) - для автономной работы

Для переключения между обычным RAG и агентским:
1. В settings добавить LLM_BACKEND=langchain_agent
2. Или использовать напрямую: from llm.langchain_agent import generate_response_stream
"""

import os
from typing import Optional, Iterator, List, Dict, Any, Callable
from dataclasses import dataclass

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
        self.mcp_server_url = self.mcp_server_url or os.getenv('MCP_SERVER_URL')


# Тип для функции поиска (инъекция зависимости)
SearchFunction = Callable[[str], List[Dict[str, Any]]]

# Глобальная функция поиска (устанавливается извне)
_search_function: Optional[SearchFunction] = None


def set_search_function(fn: SearchFunction):
    """
    Устанавливает функцию поиска для агента.
    
    Вызывается из pipeline при инициализации.
    
    Args:
        fn: Функция поиска, принимает query и возвращает список чанков
    """
    global _search_function
    _search_function = fn
    logger.info("Search function registered for agent")


def _search_via_mcp(query: str, mcp_url: str) -> List[Dict[str, Any]]:
    """Поиск через MCP-сервер."""
    import httpx
    
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{mcp_url}/tools/search_documents",
                json={"query": query, "top_k": 5}
            )
            if response.status_code == 200:
                data = response.json()
                # Преобразуем формат MCP в формат chunks
                return [
                    {
                        "content": c["content"],
                        "metadata": {
                            "file_path": c["file_path"],
                            "title": c.get("title"),
                            "summary": c.get("summary"),
                            "category": c.get("category"),
                            "chunk_index": c.get("chunk_index", 0),
                        },
                        "similarity": c.get("similarity", 0),
                    }
                    for c in data.get("chunks", [])
                ]
    except Exception as e:
        logger.error(f"MCP search error: {e}")
    return []


def _create_search_tool(config: AgentConfig = None):
    """Создаёт инструмент поиска для агента."""
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
        chunks = []
        
        # Приоритет: внедрённая функция > MCP-сервер
        if _search_function is not None:
            try:
                chunks = _search_function(query)
            except Exception as e:
                logger.error(f"Search function error: {e}")
        elif config and config.mcp_server_url:
            chunks = _search_via_mcp(query, config.mcp_server_url)
        else:
            return "Ошибка: функция поиска не настроена и MCP-сервер не указан"
        
        if not chunks:
            return "Документы по запросу не найдены"
        
        # Форматируем результаты
        results = []
        for i, chunk in enumerate(chunks, 1):
            metadata = chunk.get("metadata", {})
            file_path = metadata.get("file_path", "неизвестный источник")
            title = metadata.get("title", "")
            content = chunk.get("content", "")[:500]  # Ограничиваем длину
            similarity = chunk.get("similarity", 0)
            
            result = f"[Документ {i}] {title or file_path} (релевантность: {similarity:.2f})\n{content}"
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
    "set_search_function",
    "AgentConfig",
]
