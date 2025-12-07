"""
Pipelines для RAG-генерации ответов.

Поддерживает:
- simple: базовый RAG (поиск → промпт → генерация)

См. HOW_TO_ADD_PIPELINE.md для инструкции по добавлению нового пайплайна.
"""

from typing import Dict, Type, Optional

from logging_config import get_logger
from settings import settings
from repository import ChatRepository
from embedders import build_embedder
from vector_searchers import build_searcher

from .base import BasePipeline, RAGContext
from .simple import SimpleRAGPipeline

logger = get_logger("chat_backend.pipelines")


# Реестр доступных пайплайнов
PIPELINES: Dict[str, Type[BasePipeline]] = {
    "simple": SimpleRAGPipeline,
}


def build_pipeline(
    repository: Optional[ChatRepository] = None,
    pipeline_type: Optional[str] = None
) -> BasePipeline:
    """
    Создаёт pipeline на основе настроек.
    
    Args:
        repository: Репозиторий для работы с БД (создаётся если не передан)
        pipeline_type: Тип пайплайна (берётся из settings если не передан)
        
    Returns:
        Инстанс pipeline
    """
    # Определяем тип пайплайна
    backend = pipeline_type or settings.PIPELINE_TYPE
    
    if backend not in PIPELINES:
        logger.warning(f"Unknown pipeline '{backend}', falling back to simple")
        backend = "simple"
    
    # Создаём зависимости
    if repository is None:
        repository = ChatRepository(settings.DATABASE_URL)
    
    embedder = build_embedder()
    searcher = build_searcher(embedder, repository)
    
    # Создаём пайплайн
    logger.info(f"Using {backend} pipeline")
    
    pipeline_class = PIPELINES[backend]
    pipeline = pipeline_class(searcher=searcher, repository=repository)
    
    # Регистрируем функцию поиска для LangChain агента (если используется)
    _register_search_for_agent(searcher)
    
    return pipeline


def _register_search_for_agent(searcher):
    """Регистрирует функцию поиска для LangChain агента если он используется."""
    try:
        from llm import get_backend_name
        if get_backend_name() == "langchain_agent":
            from llm.langchain_agent import set_search_function
            set_search_function(searcher.search)
            logger.info("Search function registered for LangChain agent")
    except ImportError:
        pass  # LangChain не установлен


# Singleton instance
_pipeline_instance: Optional[BasePipeline] = None


def get_pipeline() -> BasePipeline:
    """Получить singleton пайплайна."""
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = build_pipeline()
    return _pipeline_instance


__all__ = [
    "BasePipeline",
    "RAGContext",
    "SimpleRAGPipeline", 
    "PIPELINES",
    "build_pipeline",
    "get_pipeline",
]
