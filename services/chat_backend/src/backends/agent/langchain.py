"""
LangChain Agent для Agent Backend.

Создание ReAct агента с инструментами поиска.
Агент возвращает только ответ, sources передаются отдельно.
"""
from typing import Any, List, Dict, Callable
from dataclasses import dataclass, field

from logging_config import get_logger

logger = get_logger("chat_backend.agent.langchain")


@dataclass
class SearchContext:
    """Контекст для хранения найденных документов."""
    chunks: List[Dict[str, Any]] = field(default_factory=list)
    
    def clear(self):
        self.chunks = []
    
    def add_chunks(self, chunks: List[Dict[str, Any]]):
        self.chunks.extend(chunks)


def check_langchain() -> bool:
    """Проверяет доступность LangChain."""
    try:
        from langchain_ollama import ChatOllama
        from langgraph.prebuilt import create_react_agent
        return True
    except ImportError:
        return False


def create_search_tool(
    search_func: Callable[[str, int], List[Dict[str, Any]]],
    context: SearchContext
):
    """
    Создаёт инструмент поиска для агента.
    
    Найденные документы сохраняются в context для последующей 
    передачи как sources (а не в тексте ответа).
    
    Args:
        search_func: Функция поиска (query, top_k) -> chunks
        context: Контекст для сохранения найденных документов
        
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
            
        Returns:
            Краткое описание найденных документов для формирования ответа.
            НЕ включай сырые данные документов в свой ответ — 
            пользователь увидит их как ссылки.
        """
        chunks = search_func(query, 5)
        
        if not chunks:
            return "Документы по запросу не найдены."
        
        # Сохраняем chunks в контекст для передачи как sources
        context.add_chunks(chunks)
        
        # Формируем краткое описание для агента (без полного контента)
        summaries = []
        for i, chunk in enumerate(chunks, 1):
            meta = chunk.get("metadata", {})
            title = meta.get("title") or meta.get("file_name") or "Без названия"
            category = meta.get("category") or "Документ"
            summary = meta.get("summary") or ""
            content_preview = chunk.get("content", "")[:300]
            
            summaries.append(f"[{i}] {category}: {title}")
            if summary:
                summaries.append(f"    Описание: {summary}")
            summaries.append(f"    Содержимое: {content_preview}...")
        
        logger.info(f"🔍 Agent search: '{query[:30]}...' → {len(chunks)} documents")
        
        return (
            f"Найдено {len(chunks)} документов. "
            "Используй эту информацию для ответа:\n\n" + 
            "\n\n".join(summaries) +
            "\n\nОтвечай кратко и по существу. "
            "НЕ перечисляй документы в ответе — пользователь увидит их как ссылки."
        )
    
    return search_documents


def create_agent(
    base_url: str,
    model: str,
    search_func: Callable[[str, int], List[Dict[str, Any]]],
    context: SearchContext,
    temperature: float = 0.7,
    max_tokens: int = 2048
):
    """
    Создаёт LangChain агента с инструментами.
    
    Args:
        base_url: URL Ollama API
        model: Модель LLM
        search_func: Функция поиска документов
        context: Контекст для сохранения найденных документов
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
    
    tools = [create_search_tool(search_func, context)]
    return create_react_agent(llm, tools)
