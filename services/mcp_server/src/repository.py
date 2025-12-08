"""
Repository для MCP Server — работа с PostgreSQL + pgvector.
"""

from typing import List, Dict, Any
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor

from logging_config import get_logger

logger = get_logger("mcp_server.repository")


class MCPRepository:
    """Репозиторий для работы с чанками документов."""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
    
    @contextmanager
    def get_connection(self):
        """Context manager для соединения с БД."""
        conn = psycopg2.connect(self.database_url)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def search_similar(
        self,
        embedding: List[float],
        top_k: int = 5,
        threshold: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Поиск похожих чанков по embedding.
        
        Использует cosine distance через pgvector.
        """
        embedding_str = "[" + ",".join(map(str, embedding)) + "]"
        
        query = """
            SELECT 
                content,
                metadata,
                1 - (embedding <=> %s::vector) as similarity
            FROM chunks
            WHERE 1 - (embedding <=> %s::vector) >= %s
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """
        
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (embedding_str, embedding_str, threshold, embedding_str, top_k))
                rows = cur.fetchall()
        
        results = []
        for row in rows:
            results.append({
                "content": row["content"],
                "metadata": row["metadata"] or {},
                "similarity": float(row["similarity"])
            })
        
        return results
    
    def get_chunks_by_file_path(self, file_path: str) -> List[Dict[str, Any]]:
        """Получить все чанки документа по пути."""
        query = """
            SELECT content, metadata
            FROM chunks
            WHERE metadata->>'file_path' = %s
            ORDER BY (metadata->>'chunk_index')::int
        """
        
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, (file_path,))
                rows = cur.fetchall()
        
        return [
            {"content": row["content"], "metadata": row["metadata"] or {}}
            for row in rows
        ]
    
    def count_chunks(self) -> int:
        """Количество чанков в БД."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM chunks")
                return cur.fetchone()[0]
