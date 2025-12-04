"""
PostgreSQL Repository для Chat Backend.

Изолированная реализация работы с БД, независимая от других сервисов.
Основной метод - поиск релевантных чанков по embedding.
"""

from __future__ import annotations
from contextlib import contextmanager
from typing import Dict, List, Any

import psycopg2
import psycopg2.extras

from logging_config import get_logger

logger = get_logger("chat_backend.repository")


class ChatRepository:
    """PostgreSQL репозиторий для Chat Backend."""
    
    def __init__(
        self, 
        database_url: str,
        chunks_table: str = "chunks"
    ):
        self.connection_string = database_url
        self.chunks_table = chunks_table
    
    @contextmanager
    def get_connection(self):
        """Context manager для работы с соединением."""
        conn = psycopg2.connect(self.connection_string)
        try:
            yield conn
            conn.commit()
        except Exception as exc:
            conn.rollback()
            logger.error(f"Database error: {exc}")
            raise
        finally:
            conn.close()
    
    def search_similar_chunks(
        self,
        embedding: List[float],
        limit: int = 5,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Поиск похожих чанков по embedding через pgvector.
        
        Args:
            embedding: Вектор запроса
            limit: Максимальное количество результатов
            threshold: Минимальный порог схожести (cosine similarity)
            
        Returns:
            Список чанков с контентом, метаданными и score
        """
        if not embedding:
            logger.warning("Empty embedding provided for search")
            return []
        
        try:
            embedding_str = "[" + ",".join(map(str, embedding)) + "]"
            
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    # Используем cosine distance: 1 - distance = similarity
                    # <=> - cosine distance operator в pgvector
                    cur.execute(
                        f"""
                        SELECT 
                            content,
                            metadata,
                            1 - (embedding <=> %s::vector) as similarity
                        FROM {self.chunks_table}
                        WHERE embedding IS NOT NULL
                          AND 1 - (embedding <=> %s::vector) >= %s
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s
                        """,
                        (embedding_str, embedding_str, threshold, embedding_str, limit),
                    )
                    
                    results = []
                    for row in cur.fetchall():
                        results.append({
                            "content": row["content"],
                            "metadata": row["metadata"],
                            "similarity": float(row["similarity"]),
                        })
                    
                    logger.info(f"Found {len(results)} similar chunks | threshold={threshold}")
                    return results
                    
        except Exception as exc:
            logger.error(f"Search failed: {exc}")
            return []
    
    def get_total_chunks_count(self) -> int:
        """Получить общее количество чанков в базе."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {self.chunks_table}")
                return cur.fetchone()[0]
    
    def get_unique_files_count(self) -> int:
        """Получить количество уникальных файлов в базе чанков."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT COUNT(DISTINCT metadata->>'file_hash') FROM {self.chunks_table}"
                )
                return cur.fetchone()[0]
