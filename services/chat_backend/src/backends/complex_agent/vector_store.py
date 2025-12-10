"""
Vector Store Adapter для Complex Agent.

Обёртка над PostgreSQL + pgvector для semantic и structured поиска.
НЕ использует LangChain SupabaseVectorStore — работает напрямую с psycopg2
для полного контроля над фильтрацией и запросами.
"""
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

import psycopg2
import psycopg2.extras

from logging_config import get_logger
from .schemas import SearchHit, SearchFilter, MetadataModel
from .config import STRUCTURED_SEARCH_BASE_SCORE

logger = get_logger("chat_backend.complex_agent.vector_store")


class VectorStoreAdapter:
    """
    Адаптер для работы с vector store (PostgreSQL + pgvector).
    
    Поддерживает:
    - search_semantic: поиск по embedding с optional фильтрами
    - search_structured: поиск только по метаданным (без embedding)
    """
    
    def __init__(
        self,
        database_url: str,
        table_name: str = "chunks",
        embedding_dim: int = 1024
    ):
        self.database_url = database_url
        self.table_name = table_name
        self.embedding_dim = embedding_dim
    
    @contextmanager
    def _get_connection(self):
        """Context manager для соединения с БД."""
        conn = psycopg2.connect(self.database_url)
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()
    
    def search_semantic(
        self,
        embedding: List[float],
        limit: int = 10,
        filters: Optional[SearchFilter] = None,
        threshold: float = 0.0
    ) -> List[SearchHit]:
        """
        Семантический поиск по embedding с опциональными фильтрами.
        
        Args:
            embedding: Вектор запроса
            limit: Максимум результатов
            filters: Фильтры по метаданным (category, company, person, etc.)
            threshold: Минимальный порог similarity
            
        Returns:
            Список SearchHit, отсортированный по similarity (убывание)
        """
        if not embedding:
            logger.warning("Empty embedding for semantic search")
            return []
        
        embedding_str = "[" + ",".join(map(str, embedding)) + "]"
        
        # Строим WHERE условия и параметры для фильтров
        filter_clauses = []
        filter_params = []
        
        if filters and not filters.is_empty():
            filter_clauses, filter_params = self._build_filter_clauses(filters)
        
        # Базовые условия
        where_clauses = ["embedding IS NOT NULL"]
        where_clauses.extend(filter_clauses)
        where_sql = " AND ".join(where_clauses)
        
        # Параметры в правильном порядке:
        # 1. SELECT similarity - embedding_str
        # 2. WHERE фильтры - filter_params
        # 3. WHERE similarity comparison - embedding_str
        # 4. WHERE threshold - threshold
        # 5. ORDER BY - embedding_str
        # 6. LIMIT - limit
        params = [embedding_str] + filter_params + [embedding_str, threshold, embedding_str, limit]
        
        query = f"""
            SELECT 
                content,
                metadata,
                1 - (embedding <=> %s::vector) as similarity
            FROM {self.table_name}
            WHERE {where_sql}
              AND 1 - (embedding <=> %s::vector) >= %s
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """
        
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(query, params)
                    
                    results = []
                    for row in cur.fetchall():
                        results.append(SearchHit(
                            content=row["content"],
                            metadata=MetadataModel.from_dict(row["metadata"]),
                            base_score=float(row["similarity"]),
                        ))
                    
                    logger.debug(f"Semantic search: {len(results)} results | filters={filters}")
                    return results
                    
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []
    
    def search_structured(
        self,
        filters: SearchFilter,
        limit: int = 10
    ) -> List[SearchHit]:
        """
        Структурированный поиск только по метаданным (без embedding).
        
        Используется когда есть точные фильтры (category, company, etc.).
        Результаты получают base_score = STRUCTURED_SEARCH_BASE_SCORE.
        
        Args:
            filters: Фильтры по метаданным
            limit: Максимум результатов
            
        Returns:
            Список SearchHit
        """
        if filters.is_empty():
            logger.debug("Empty filters for structured search, skipping")
            return []
        
        # Строим WHERE условия из фильтров
        filter_clauses, params = self._build_filter_clauses(filters)
        
        # Базовое условие + фильтры
        where_clauses = ["1=1"] + filter_clauses
        params.append(limit)
        
        where_sql = " AND ".join(where_clauses)
        
        query = f"""
            SELECT content, metadata
            FROM {self.table_name}
            WHERE {where_sql}
            ORDER BY (metadata->>'modified_at') DESC NULLS LAST
            LIMIT %s
        """
        
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(query, params)
                    
                    results = []
                    for row in cur.fetchall():
                        results.append(SearchHit(
                            content=row["content"],
                            metadata=MetadataModel.from_dict(row["metadata"]),
                            base_score=STRUCTURED_SEARCH_BASE_SCORE,
                        ))
                    
                    logger.debug(f"Structured search: {len(results)} results | filters={filters}")
                    return results
                    
        except Exception as e:
            logger.error(f"Structured search failed: {e}")
            return []
    
    def search_by_entity_like(
        self,
        entity: str,
        limit: int = 10
    ) -> List[SearchHit]:
        """
        Поиск по entity через SQL LIKE (fallback для semantic search).
        
        Ищет entity в:
        1. metadata->entities (JSONB array) — name поле
        2. content (полнотекстовый LIKE)
        
        Используется когда semantic search не нашёл точных совпадений.
        
        Args:
            entity: Название компании или ФИО
            limit: Максимум результатов
            
        Returns:
            Список SearchHit
        """
        if not entity:
            return []
        
        query = f"""
            SELECT content, metadata
            FROM {self.table_name}
            WHERE 
                EXISTS (
                    SELECT 1 FROM jsonb_array_elements(metadata->'entities') e
                    WHERE LOWER(e->>'name') LIKE LOWER(%s)
                )
                OR LOWER(content) LIKE LOWER(%s)
            ORDER BY (metadata->>'modified_at') DESC NULLS LAST
            LIMIT %s
        """
        
        like_pattern = f"%{entity}%"
        
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(query, [like_pattern, like_pattern, limit])
                    
                    results = []
                    for row in cur.fetchall():
                        results.append(SearchHit(
                            content=row["content"],
                            metadata=MetadataModel.from_dict(row["metadata"]),
                            base_score=STRUCTURED_SEARCH_BASE_SCORE,
                        ))
                    
                    logger.debug(f"Entity LIKE search: {len(results)} results | entity={entity}")
                    return results
                    
        except Exception as e:
            logger.error(f"Entity LIKE search failed: {e}")
            return []
    
    def _build_filter_clauses(
        self,
        filters: SearchFilter
    ) -> tuple[List[str], List[Any]]:
        """
        Построить WHERE условия и параметры из фильтров.
        
        ВАЖНО: entity НЕ используется как SQL фильтр!
        Entity добавляется в query для semantic search (embedding).
        Это позволяет найти "Акпан", "АкпанОМ", "АКПАН" и т.д.
        
        Args:
            filters: Фильтры поиска
            
        Returns:
            (clauses, params) — списки условий и параметров
        """
        clauses = []
        params = []
        
        # Category - точное совпадение (SQL фильтр)
        if filters.category:
            clauses.append("metadata->>'category' = %s")
            params.append(filters.category)
        
        # Entity — НЕ SQL фильтр! Используется для обогащения embedding query.
        # Закомментировано намеренно — entity ищется семантически через embedding.
        # if filters.entity:
        #     clauses.append(...)
        
        # Keywords — НЕ SQL фильтр! Тоже добавляется в embedding query.
        # Закомментировано — keywords ищутся семантически.
        # if filters.keywords:
        #     ...
        
        # Date range
        if filters.date_from:
            clauses.append("metadata->>'modified_at' >= %s")
            params.append(filters.date_from)
        
        if filters.date_to:
            clauses.append("metadata->>'modified_at' <= %s")
            params.append(filters.date_to + "T23:59:59")
        
        return clauses, params
    
    def get_embedding(self, text: str, ollama_url: str, model: str) -> List[float]:
        """
        Получить embedding через Ollama.
        
        Args:
            text: Текст для эмбеддинга
            ollama_url: URL Ollama API
            model: Модель эмбеддинга (bge-m3)
            
        Returns:
            Вектор эмбеддинга
        """
        import requests
        
        try:
            response = requests.post(
                f"{ollama_url}/api/embeddings",
                json={"model": model, "prompt": text},
                timeout=60
            )
            
            if response.status_code == 200:
                return response.json().get("embedding", [])
            else:
                logger.error(f"Ollama embedding failed: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Embedding request failed: {e}")
            return []
