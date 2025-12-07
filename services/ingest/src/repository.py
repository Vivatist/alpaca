"""
PostgreSQL Repository для Ingest Service.

Изолированная реализация работы с БД, независимая от core/.
"""

from __future__ import annotations
from contextlib import contextmanager
from typing import Dict, List, Optional, Any

import psycopg2
import psycopg2.extras

from logging_config import get_logger
from contracts import SyncStatus

logger = get_logger("ingest.repository")


class IngestRepository:
    """PostgreSQL репозиторий для Ingest Service."""
    
    def __init__(
        self, 
        database_url: str,
        files_table: str = "files",
        chunks_table: str = "chunks"
    ):
        self.connection_string = database_url
        self.files_table = files_table
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
    
    # === Status management ===
    
    def mark_as_ok(self, file_hash: str) -> bool:
        """Пометить файл как успешно обработанный."""
        return self._update_status(file_hash, SyncStatus.OK)
    
    def mark_as_error(self, file_hash: str) -> bool:
        """Пометить файл как ошибочный."""
        return self._update_status(file_hash, SyncStatus.ERROR)
    
    def mark_as_processed(self, file_hash: str) -> bool:
        """Пометить файл как находящийся в обработке."""
        return self._update_status(file_hash, SyncStatus.PROCESSED)
    
    def _update_status(self, file_hash: str, status: SyncStatus) -> bool:
        """Обновить статус файла."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        UPDATE {self.files_table}
                        SET status_sync = %s, last_checked = CURRENT_TIMESTAMP
                        WHERE hash = %s
                        """,
                        (status.value, file_hash),
                    )
                    return cur.rowcount > 0
        except Exception as exc:
            logger.error(f"Failed to update status to {status} for {file_hash}: {exc}")
            return False
    
    # === File management ===
    
    def delete_file_by_hash(self, file_hash: str) -> bool:
        """Удалить запись о файле по хэшу."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"DELETE FROM {self.files_table} WHERE hash = %s",
                    (file_hash,),
                )
                return cur.rowcount > 0
    
    def set_raw_text(self, file_hash: str, raw_text: str) -> bool:
        """Сохранить raw_text файла."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE {self.files_table}
                    SET raw_text = %s, last_checked = CURRENT_TIMESTAMP
                    WHERE hash = %s
                    """,
                    (raw_text, file_hash),
                )
                return cur.rowcount > 0
    
    # === Chunk management ===
    
    def delete_chunks_by_hash(self, file_hash: str) -> int:
        """Удалить все чанки файла по хэшу."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"DELETE FROM {self.chunks_table} WHERE metadata->>'file_hash' = %s",
                    (file_hash,),
                )
                return cur.rowcount
    
    def save_chunk(
        self, 
        content: str, 
        metadata: Dict[str, Any], 
        embedding: Optional[List[float]] = None
    ) -> bool:
        """Сохранить чанк с метаданными и эмбеддингом."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                if embedding is not None:
                    embedding_str = "[" + ",".join(map(str, embedding)) + "]"
                    cur.execute(
                        f"""
                        INSERT INTO {self.chunks_table} (content, metadata, embedding)
                        VALUES (%s, %s, %s::vector)
                        """,
                        (content, psycopg2.extras.Json(metadata), embedding_str),
                    )
                else:
                    cur.execute(
                        f"""
                        INSERT INTO {self.chunks_table} (content, metadata)
                        VALUES (%s, %s)
                        """,
                        (content, psycopg2.extras.Json(metadata)),
                    )
                return True
    
    def get_chunks_count(self, file_hash: str) -> int:
        """Получить количество чанков для файла."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT COUNT(*) FROM {self.chunks_table} WHERE metadata->>'file_hash' = %s",
                    (file_hash,),
                )
                return cur.fetchone()[0]
    
    # === Utility ===
    
    def reset_processed_to_added(self) -> int:
        """Сбросить зависшие 'processed' статусы в 'added'."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE {self.files_table}
                    SET status_sync = 'added'
                    WHERE status_sync = 'processed'
                    """
                )
                return cur.rowcount
