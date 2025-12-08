"""
LangChain Agent для Agent Backend.

Создание ReAct агента с инструментами поиска.
"""
from typing import Any, List, Dict, Callable

from logging_config import get_logger

logger = get_logger("chat_backend.agent.langchain")


def check_langchain() -> bool:
    """Проверяет доступность LangChain."""
    try:
        from langchain_ollama import ChatOllama
        from langgraph.prebuilt import create_react_agent
        return True
    except ImportError:
        return False


def create_search_tool(search_func: Callable[[str, int], List[Dict[str, Any]]]):
    """
    Создаёт инструмент поиска для агента.
    
    Args:
        search_func: Функция поиска (query, top_k) -> chunks
        
    Returns:
        LangChain tool
    """
    from langchain_core.tools import tool
    
    @tool
    def search_documents(query: str) -> str:
        """
        Поиск релевантных документов в базе знаний компании.
        Используй когда нужно найти информацию в документах, договорах, письмах.
        
        Args:
            query: Поисковый запрос на естественном языке
        """
        chunks = search_func(query, 5)
        
        if not chunks:
            return "Документы по запросу не найдены"
        
        results = []
        for i, chunk in enumerate(chunks, 1):
            meta = chunk.get("metadata", {})
            title = meta.get("title") or meta.get("file_name") or meta.get("file_path", "?")
            content = chunk.get("content", "")[:500]
            similarity = chunk.get("similarity", 0)
            results.append(f"[Документ {i}] {title} ({similarity:.2f})\n{content}")
        
        logger.info(f"🔍 Agent search: '{query[:30]}...' → {len(results)} results")
        return "\n\n---\n\n".join(results)
    
    return search_documents


def create_agent(
    base_url: str,
    model: str,
    search_func: Callable[[str, int], List[Dict[str, Any]]],
    temperature: float = 0.7,
    max_tokens: int = 2048
):
    """
    Создаёт LangChain агента с инструментами.
    
    Args:
        base_url: URL Ollama API
        model: Модель LLM
        search_func: Функция поиска документов
        temperature: Температура генерации
        max_tokens: Максимум токенов
        
    Returns:
        LangGraph agent
    """
    from langchain_ollama import ChatOllama
    from langgraph.prebuilt import create_react_agent
    
    llm = ChatOllama(
        model=model,
        base_url=base_url,
        temperature=temperature,
        num_predict=max_tokens,
    )
    
    tools = [create_search_tool(search_func)]
    return create_react_agent(llm, tools)
