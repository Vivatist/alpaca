"""
LangChain Tool для поиска документов.

SearchDocumentsTool — инструмент для агента, вызывающий robust_search.
"""
from typing import List, Optional, Any, Type, Callable
from pydantic import BaseModel, Field

from logging_config import get_logger
from .schemas import SearchFilter, SearchResult, RetryDebugInfo
from .vector_store import VectorStoreAdapter
from .robust_search import robust_search, StreamCallback
from .config import DOCUMENT_CATEGORIES, DEFAULT_SEARCH_LIMIT

logger = get_logger("chat_backend.complex_agent.search_tool")


# === Tool Input Schema ===

class SearchDocumentsInput(BaseModel):
    """Схема входных параметров для инструмента поиска."""
    
    query: str = Field(
        description="Поисковый запрос — текст для семантического поиска"
    )
    category: Optional[str] = Field(
        default=None,
        description=f"Категория документа. Одно из: {', '.join(DOCUMENT_CATEGORIES)}"
    )
    company: Optional[str] = Field(
        default=None,
        description="Название компании для фильтрации"
    )
    person: Optional[str] = Field(
        default=None,
        description="ФИО человека для фильтрации"
    )
    keywords: Optional[List[str]] = Field(
        default=None,
        description="Список ключевых слов для фильтрации"
    )
    date_from: Optional[str] = Field(
        default=None,
        description="Начало периода в формате YYYY-MM-DD"
    )
    date_to: Optional[str] = Field(
        default=None,
        description="Конец периода в формате YYYY-MM-DD"
    )
    limit: int = Field(
        default=DEFAULT_SEARCH_LIMIT,
        description="Максимальное количество результатов"
    )


# === Search Tool Factory ===

def create_search_tool(
    vector_store: VectorStoreAdapter,
    ollama_url: str,
    embedding_model: str,
    stream_callback: Optional[StreamCallback] = None
):
    """
    Создать LangChain Tool для поиска документов.
    
    Args:
        vector_store: Адаптер vector store
        ollama_url: URL Ollama API
        embedding_model: Модель для эмбеддингов
        stream_callback: Callback для промежуточных сообщений
        
    Returns:
        LangChain StructuredTool
    """
    try:
        from langchain_core.tools import StructuredTool
    except ImportError:
        logger.error("langchain-core not installed")
        raise ImportError("Install langchain-core: pip install langchain-core")
    
    # Контекст для хранения результатов последнего поиска
    search_context = SearchContext()
    
    def _search(
        query: str,
        category: Optional[str] = None,
        company: Optional[str] = None,
        person: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = DEFAULT_SEARCH_LIMIT
    ) -> str:
        """Выполнить поиск документов."""
        
        # Валидация категории
        if category and category not in DOCUMENT_CATEGORIES:
            # Пытаемся найти похожую
            category_lower = category.lower()
            matched = None
            for cat in DOCUMENT_CATEGORIES:
                if cat.lower() in category_lower or category_lower in cat.lower():
                    matched = cat
                    break
            category = matched
        
        # Строим фильтры
        filters = SearchFilter(
            category=category,
            company=company,
            person=person,
            keywords=keywords,
            date_from=date_from,
            date_to=date_to,
        )
        
        # Получаем embedding запроса
        embedding = vector_store.get_embedding(query, ollama_url, embedding_model)
        
        if not embedding:
            return "Ошибка: не удалось создать embedding для запроса"
        
        # Выполняем robust search
        results, debug_info = robust_search(
            vector_store=vector_store,
            embedding=embedding,
            filters=filters,
            limit=limit,
            stream_callback=stream_callback
        )
        
        # Сохраняем результаты в контекст
        search_context.results = results
        search_context.debug_info = debug_info
        
        if not results:
            return "Документы не найдены"
        
        # Форматируем результаты для LLM
        return _format_results_for_llm(results)
    
    tool = StructuredTool.from_function(
        func=_search,
        name="search_documents",
        description="""Поиск документов по семантическому запросу и фильтрам.

Используй этот инструмент для поиска информации в документах компании.

Параметры:
- query (обязательный): текст запроса для семантического поиска
- category: категория документа (Договор подряда, Трудовой договор, и т.д.)
- company: название компании
- person: ФИО человека
- keywords: список ключевых слов
- date_from: начало периода (YYYY-MM-DD)
- date_to: конец периода (YYYY-MM-DD)
- limit: максимум результатов (по умолчанию 10)

Возвращает найденные фрагменты документов с метаданными.""",
        args_schema=SearchDocumentsInput,
        return_direct=False,
    )
    
    # Привязываем контекст к tool
    tool._search_context = search_context
    
    return tool


class SearchContext:
    """Контекст для хранения результатов поиска."""
    
    def __init__(self):
        self.results: List[SearchResult] = []
        self.debug_info: Optional[RetryDebugInfo] = None
    
    def clear(self):
        """Очистить контекст."""
        self.results = []
        self.debug_info = None


def _format_results_for_llm(results: List[SearchResult]) -> str:
    """
    Форматировать результаты поиска для LLM.
    
    Возвращает текст с содержимым документов и метаданными.
    """
    parts = [f"Найдено {len(results)} документов:\n"]
    
    for i, result in enumerate(results, 1):
        meta = result.metadata
        
        # Заголовок документа
        title = meta.title or meta.file_path.split("/")[-1]
        parts.append(f"\n--- Документ {i}: {title} ---")
        
        # Метаданные
        if meta.category:
            parts.append(f"Категория: {meta.category}")
        if meta.modified_at:
            parts.append(f"Дата: {meta.modified_at[:10]}")
        if meta.summary:
            parts.append(f"Описание: {meta.summary}")
        
        # Содержимое (первые 500 символов)
        content = result.content[:500]
        if len(result.content) > 500:
            content += "..."
        parts.append(f"\nСодержимое:\n{content}")
    
    return "\n".join(parts)
