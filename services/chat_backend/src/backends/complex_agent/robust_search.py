"""
Robust Search — итеративный поиск с ослаблением фильтров.

Стратегия:
1. Итерация 1: Все фильтры (strict)
2. Итерация 2: Ослабление фильтров (убираем keywords → company/person → category)
3. Итерация 3: Fallback — только semantic search без фильтров

На каждой итерации вызывается stream_callback с человеческим сообщением.
"""
from datetime import datetime, timedelta
from typing import List, Optional, Callable, Tuple, Set

from logging_config import get_logger
from .schemas import (
    SearchHit, SearchResult, SearchFilter, 
    RetryDebugInfo, MetadataModel
)
from .vector_store import VectorStoreAdapter
from .reranker import rerank_results
from .config import (
    MIN_RESULTS_THRESHOLD,
    MAX_SEARCH_ITERATIONS,
    DATE_RANGE_EXPANSION_DAYS,
    DEFAULT_SEARCH_LIMIT,
)

logger = get_logger("chat_backend.complex_agent.robust_search")


StreamCallback = Callable[[str], None]


def robust_search(
    vector_store: VectorStoreAdapter,
    embedding: List[float],
    filters: SearchFilter,
    limit: int = DEFAULT_SEARCH_LIMIT,
    stream_callback: Optional[StreamCallback] = None
) -> Tuple[List[SearchResult], RetryDebugInfo]:
    """
    Робастный поиск с итеративным ослаблением фильтров.
    
    Args:
        vector_store: Адаптер vector store
        embedding: Embedding запроса
        filters: Начальные фильтры
        limit: Максимум результатов
        stream_callback: Callback для промежуточных сообщений
        
    Returns:
        (results, debug_info) — финальные результаты и отладочная информация
    """
    debug = RetryDebugInfo()
    
    # Итерация 1: Строгий поиск со всеми фильтрами
    _notify(stream_callback, _describe_search(filters))
    
    results = _search_iteration(
        vector_store, embedding, filters, limit, debug,
        dropped_filters=[]
    )
    
    if len(results) >= MIN_RESULTS_THRESHOLD:
        _notify(stream_callback, f"✅ Найдено {len(results)} документов")
        return results, debug
    
    # Итерация 2: Ослабление фильтров
    if debug.attempts < MAX_SEARCH_ITERATIONS:
        relaxed_filters, dropped = _relax_filters(filters, stream_callback)
        
        if dropped:
            results = _search_iteration(
                vector_store, embedding, relaxed_filters, limit, debug,
                dropped_filters=dropped
            )
            
            if len(results) >= MIN_RESULTS_THRESHOLD:
                _notify(stream_callback, f"✅ Найдено {len(results)} документов после ослабления фильтров")
                return results, debug
    
    # Итерация 3: Fallback — только semantic search
    if debug.attempts < MAX_SEARCH_ITERATIONS:
        _notify(stream_callback, "🔍 Выполняю расширенный семантический поиск...")
        debug.fallback_used = True
        
        results = _search_iteration(
            vector_store, embedding, SearchFilter(), limit, debug,
            dropped_filters=["all_filters"]
        )
        
        if results:
            _notify(stream_callback, f"✅ Найдено {len(results)} документов")
        else:
            _notify(stream_callback, "⚠️ Документы не найдены")
    
    return results, debug


def _search_iteration(
    vector_store: VectorStoreAdapter,
    embedding: List[float],
    filters: SearchFilter,
    limit: int,
    debug: RetryDebugInfo,
    dropped_filters: List[str]
) -> List[SearchResult]:
    """
    Одна итерация поиска: semantic + structured → merge → rerank.
    """
    all_hits: List[SearchHit] = []
    seen_chunks: Set[str] = set()  # Для дедупликации по file_path + chunk_index
    
    # 1. Semantic search
    semantic_hits = vector_store.search_semantic(
        embedding=embedding,
        limit=limit * 2,  # Берём больше для объединения
        filters=filters if not filters.is_empty() else None
    )
    
    for hit in semantic_hits:
        key = f"{hit.metadata.file_path}:{hit.metadata.chunk_index}"
        if key not in seen_chunks:
            seen_chunks.add(key)
            all_hits.append(hit)
    
    # 2. Structured search (только если есть фильтры)
    if not filters.is_empty():
        structured_hits = vector_store.search_structured(
            filters=filters,
            limit=limit
        )
        
        for hit in structured_hits:
            key = f"{hit.metadata.file_path}:{hit.metadata.chunk_index}"
            if key not in seen_chunks:
                seen_chunks.add(key)
                all_hits.append(hit)
    
    # 3. Rerank
    results = rerank_results(all_hits, top_k=limit)
    
    # 4. Записываем debug info
    debug.add_attempt(
        used_filters=filters.to_dict(),
        dropped_filters=dropped_filters,
        message=f"Found {len(results)} results"
    )
    
    logger.info(f"Search iteration {debug.attempts}: {len(results)} results | filters={filters.to_dict()}")
    
    return results


def _relax_filters(
    filters: SearchFilter,
    stream_callback: Optional[StreamCallback]
) -> Tuple[SearchFilter, List[str]]:
    """
    Ослабить фильтры по приоритету.
    
    Порядок ослабления:
    1. keywords (наименее точный)
    2. company/person (средняя точность)
    3. category (высокая точность)
    4. date_from/date_to — расширяем диапазон
    
    Returns:
        (relaxed_filters, dropped_filter_names)
    """
    dropped = []
    relaxed = filters.model_copy()
    
    # 1. Убираем keywords
    if relaxed.keywords:
        relaxed.keywords = None
        dropped.append("keywords")
        _notify(stream_callback, "📋 Убираю фильтр по ключевым словам...")
    
    # 2. Убираем company/person
    if relaxed.company:
        relaxed.company = None
        dropped.append("company")
        _notify(stream_callback, "🏢 Убираю фильтр по компании...")
    
    if relaxed.person:
        relaxed.person = None
        dropped.append("person")
        _notify(stream_callback, "👤 Убираю фильтр по персоне...")
    
    # 3. Расширяем диапазон дат
    if relaxed.date_from or relaxed.date_to:
        relaxed = _expand_date_range(relaxed, stream_callback)
        dropped.append("date_expanded")
    
    # 4. Убираем category (последний resort)
    if relaxed.category and len(dropped) < 2:
        relaxed.category = None
        dropped.append("category")
        _notify(stream_callback, "📁 Убираю фильтр по категории...")
    
    return relaxed, dropped


def _expand_date_range(
    filters: SearchFilter,
    stream_callback: Optional[StreamCallback]
) -> SearchFilter:
    """Расширить диапазон дат на ±1 год."""
    relaxed = filters.model_copy()
    
    try:
        if relaxed.date_from:
            dt = datetime.strptime(relaxed.date_from, "%Y-%m-%d")
            new_date = dt - timedelta(days=DATE_RANGE_EXPANSION_DAYS)
            relaxed.date_from = new_date.strftime("%Y-%m-%d")
        
        if relaxed.date_to:
            dt = datetime.strptime(relaxed.date_to, "%Y-%m-%d")
            new_date = dt + timedelta(days=DATE_RANGE_EXPANSION_DAYS)
            relaxed.date_to = new_date.strftime("%Y-%m-%d")
        
        _notify(stream_callback, f"📅 Расширяю временной диапазон до {relaxed.date_from or '...'} — {relaxed.date_to or '...'}")
        
    except ValueError:
        pass
    
    return relaxed


def _describe_search(filters: SearchFilter) -> str:
    """Создать человекочитаемое описание поиска."""
    parts = ["🔍 Ищу документы"]
    
    if filters.category:
        parts.append(f"категории «{filters.category}»")
    
    if filters.company:
        parts.append(f"компании «{filters.company}»")
    
    if filters.person:
        parts.append(f"с упоминанием «{filters.person}»")
    
    if filters.keywords:
        kw = ", ".join(filters.keywords[:3])
        parts.append(f"по ключевым словам: {kw}")
    
    if filters.date_from or filters.date_to:
        date_range = f"{filters.date_from or '...'} — {filters.date_to or '...'}"
        parts.append(f"за период {date_range}")
    
    if len(parts) == 1:
        parts.append("по вашему запросу...")
    else:
        parts[0] = "🔍 Ищу документы"
    
    return " ".join(parts) + "..."


def _notify(callback: Optional[StreamCallback], message: str):
    """Отправить сообщение через callback если он есть."""
    if callback:
        callback(message)
    logger.debug(f"Stream: {message}")
