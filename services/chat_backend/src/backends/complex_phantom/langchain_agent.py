"""
LangChain Agent для Complex Phantom Backend.

ReAct агент который сам решает когда искать документы.
На простые вопросы отвечает напрямую.
"""
from typing import Any, List, Dict, Callable
from dataclasses import dataclass, field

from logging_config import get_logger

logger = get_logger("chat_backend.complex_phantom.langchain")


DEFAULT_SYSTEM_PROMPT = """Ты — полезный ассистент компании ALPACA. 
У тебя есть инструмент search_documents для поиска информации в документах компании.

Правила:
1. Если вопрос требует информации из документов — используй search_documents
2. Если вопрос общий или не требует поиска — отвечай напрямую (математика, факты, перевод и т.д.)
3. НЕ выдумывай информацию о документах — ищи через инструмент
4. Отвечай на русском языке, кратко и по делу
5. НЕ перечисляй найденные документы в ответе — пользователь увидит их как ссылки под сообщением
6. Давай конкретный ответ на основе содержимого документов, без цитирования названий файлов"""


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
    
    Args:
        search_func: Функция поиска (query, top_k) -> chunks
        context: Контекст для сохранения найденных документов
    """
    from langchain_core.tools import tool
    
    @tool
    def search_documents(query: str) -> str:
        """
        Поиск релевантных документов в базе знаний компании.
        Используй когда нужно найти информацию в документах, договорах, письмах.
        НЕ используй для общих вопросов типа математики, переводов, определений.
        
        Args:
            query: Поисковый запрос на естественном языке
        """
        chunks = search_func(query, 5)
        
        if not chunks:
            return "Документы по запросу не найдены."
        
        # Сохраняем chunks в контекст для передачи как sources
        context.add_chunks(chunks)
        
        # Формируем краткое описание для агента
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
        
        logger.info(f"🔍 Search: '{query[:30]}...' → {len(chunks)} documents")
        
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
