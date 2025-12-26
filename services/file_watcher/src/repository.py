"""
Локальный репозиторий для FileWatcher.

Изолированная реализация работы с БД без зависимости от core/.
Содержит только методы, необходимые для FileWatcher:
- sync_by_hash() — синхронизация файлов с диска
- get_next_file() — получение следующего файла из очереди
- get_queue_stats() — статистика очереди
- get_file_state_records() — список файлов для VectorSync
- get_documents_records() — список чанков для VectorSync
- update_status_sync_batch() — пакетное обновление статусов
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Any, Optional, Iterable

import psycopg2
import psycopg2.extras

import logging
logger = logging.getLogger(__name__)


class FileStatus(str, Enum):
    """Статусы синхронизации файлов."""
    OK = "ok"
    ADDED = "added"
    UPDATED = "updated"
    DELETED = "deleted"
    PROCESSED = "processed"
    ERROR = "error"


@dataclass
class FileQueueItem:
    """Файл из очереди на обработку."""
    path: str
    hash: str
    size: int
    mtime: float
    status_sync: str
    last_checked: Optional[str] = None
    
    def as_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "hash": self.hash,
            "size": self.size,
            "mtime": self.mtime,
            "status_sync": self.status_sync,
            "last_checked": str(self.last_checked) if self.last_checked else None,
        }


class FileWatcherRepository:
    """PostgreSQL репозиторий для FileWatcher (изолированный от core/)."""

    def __init__(
        self,
        database_url: Optional[str] = None,
        files_table: str = "files",
        chunks_table: str = "chunks",
    ):
        self.connection_string = database_url or os.getenv("DATABASE_URL")
        self.files_table = files_table
        self.chunks_table = chunks_table
        
        try:
            self._ensure_tables()
        except psycopg2.OperationalError as e:
            error_msg = str(e)
            if "refused" in error_msg.lower() or "connect" in error_msg.lower():
                logger.error(f"❌ Cannot connect to database at {self.connection_string}")
                logger.error(f"   Ensure PostgreSQL is running and DATABASE_URL is correct")
                logger.error(f"   Error: {error_msg}")
            else:
                logger.error(f"❌ Database operational error: {error_msg}")
            raise
        except psycopg2.DatabaseError as e:
            logger.error(f"❌ Database error during initialization: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Unexpected error during database initialization: {e}")
            raise

    @contextmanager
    def get_connection(self):
        """Context manager для работы с БД."""
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

    def _ensure_tables(self) -> None:
        """Создаёт таблицы и индексы если не существуют."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.files_table} (
                        id SERIAL PRIMARY KEY,
                        path TEXT NOT NULL UNIQUE,
                        size BIGINT NOT NULL,
                        hash TEXT,
                        mtime DOUBLE PRECISION,
                        status_sync TEXT DEFAULT 'ok',
                        last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        raw_text TEXT
                    )
                """)
                cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.files_table}_path ON {self.files_table}(path)")
                cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.files_table}_hash ON {self.files_table}(hash)")
                cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.files_table}_status_sync ON {self.files_table}(status_sync)")

    # -------------------------------------------------------------------------
    # Синхронизация файловой системы
    # -------------------------------------------------------------------------

    def sync_by_hash(self, disk_files: List[Dict[str, Any]]) -> Dict[str, int]:
        """Синхронизирует список файлов с диска с БД.
        
        Args:
            disk_files: Список файлов [{path, hash, size, mtime}, ...]
            
        Returns:
            Статистика {added, updated, unchanged, deleted}
        """
        stats = {"added": 0, "updated": 0, "unchanged": 0, "deleted": 0}

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Получаем текущее состояние БД
                cur.execute(f"SELECT path, hash, status_sync FROM {self.files_table}")
                db_records = {row[0]: {"hash": row[1], "status": row[2]} for row in cur.fetchall()}
                disk_paths = {f["path"]: f for f in disk_files}

                inserts: List[tuple] = []
                status_updates: List[tuple] = []
                full_updates: List[tuple] = []

                for disk_path, disk_file in disk_paths.items():
                    if disk_path not in db_records:
                        # Новый файл
                        inserts.append((
                            disk_path,
                            disk_file["size"],
                            disk_file["hash"],
                            disk_file["mtime"],
                        ))
                        stats["added"] += 1
                        continue

                    db_record = db_records[disk_path]
                    hash_matches = db_record["hash"] == disk_file["hash"]
                    action, new_status = self._decide_action(db_record["status"], hash_matches)

                    if action == "skip":
                        stats["unchanged"] += 1
                    elif action == "update_status" and new_status:
                        status_updates.append((new_status, disk_path))
                        stats["updated"] += 1
                    elif action == "update_full" and new_status:
                        full_updates.append((
                            disk_file["hash"],
                            disk_file["size"],
                            disk_file["mtime"],
                            new_status,
                            disk_path,
                        ))
                        stats["updated"] += 1

                # Batch insert новых файлов
                if inserts:
                    psycopg2.extras.execute_values(
                        cur,
                        f"""
                        INSERT INTO {self.files_table} (path, size, hash, mtime, last_checked, status_sync)
                        VALUES %s
                        """,
                        inserts,
                        template="(%s, %s, %s, %s, CURRENT_TIMESTAMP, 'added')",
                        page_size=500,
                    )

                # Batch update статусов
                if status_updates:
                    cur.executemany(
                        f"""
                        UPDATE {self.files_table}
                        SET status_sync = %s, last_checked = CURRENT_TIMESTAMP
                        WHERE path = %s
                        """,
                        status_updates,
                    )

                # Batch update с полными данными
                if full_updates:
                    cur.executemany(
                        f"""
                        UPDATE {self.files_table}
                        SET hash = %s, size = %s, mtime = %s, status_sync = %s, last_checked = CURRENT_TIMESTAMP
                        WHERE path = %s
                        """,
                        full_updates,
                    )

                # Помечаем удалённые файлы
                missing_paths = set(db_records.keys()) - set(disk_paths.keys())
                if missing_paths:
                    paths_to_delete = [
                        path for path in missing_paths
                        if db_records[path]["status"] != FileStatus.DELETED.value
                    ]
                    if paths_to_delete:
                        cur.execute(
                            f"""
                            UPDATE {self.files_table}
                            SET status_sync = 'deleted', last_checked = CURRENT_TIMESTAMP
                            WHERE path = ANY(%s)
                            """,
                            (paths_to_delete,),
                        )
                        stats["deleted"] = cur.rowcount

        return stats

    def _decide_action(self, current_status: Optional[str], hash_matches: bool) -> tuple[str, Optional[str]]:
        """Определяет действие для существующего файла."""
        if hash_matches:
            if current_status == FileStatus.DELETED.value:
                return "update_status", FileStatus.UPDATED.value
            if current_status in (
                FileStatus.ADDED.value,
                FileStatus.UPDATED.value,
                FileStatus.PROCESSED.value,
                FileStatus.OK.value,
                FileStatus.ERROR.value,
            ):
                return "skip", None
            if current_status is None:
                return "update_status", FileStatus.UPDATED.value
        else:
            return "update_full", FileStatus.UPDATED.value
        return "skip", None

    # -------------------------------------------------------------------------
    # Очередь обработки
    # -------------------------------------------------------------------------

    def get_next_file(self) -> Optional[FileQueueItem]:
        """Получает следующий файл для обработки.
        
        Приоритет: deleted > updated > added
        
        ВАЖНО: Этот метод НЕ меняет статус файла!
        Worker должен сам пометить файл как 'processed' после получения.
        
        Returns:
            FileQueueItem или None если очередь пуста
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT path, hash, size, mtime, status_sync, last_checked
                    FROM {self.files_table}
                    WHERE status_sync IN ('deleted', 'updated', 'added')
                    ORDER BY
                        CASE status_sync
                            WHEN 'deleted' THEN 1
                            WHEN 'updated' THEN 2
                            ELSE 3
                        END,
                        last_checked
                    LIMIT 1
                """)
                row = cur.fetchone()
                if row:
                    return FileQueueItem(
                        path=row[0],
                        hash=row[1],
                        size=row[2],
                        mtime=row[3],
                        status_sync=row[4],
                        last_checked=row[5],
                    )
                return None

    def get_queue_stats(self) -> Dict[str, int]:
        """Возвращает статистику очереди по статусам."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT status_sync, COUNT(*)
                    FROM {self.files_table}
                    GROUP BY status_sync
                """)
                return {row[0] or "unknown": row[1] for row in cur.fetchall()}

    # -------------------------------------------------------------------------
    # VectorSync методы
    # -------------------------------------------------------------------------

    def get_file_state_records(self) -> List[tuple]:
        """Возвращает все записи из таблицы files для VectorSync."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT path, hash, status_sync FROM {self.files_table}")
                return cur.fetchall()

    def get_documents_records(self) -> List[tuple]:
        """Возвращает уникальные файлы из таблицы chunks для VectorSync."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    SELECT metadata->>'file_hash' as hash,
                           metadata->>'file_path' as path,
                           COUNT(*)
                    FROM {self.chunks_table}
                    WHERE metadata->>'file_hash' IS NOT NULL
                      AND metadata->>'file_path' IS NOT NULL
                    GROUP BY metadata->>'file_hash', metadata->>'file_path'
                """)
                return cur.fetchall()

    def update_status_sync_batch(self, updates: Iterable[tuple[str, str]]) -> int:
        """Пакетное обновление статусов.
        
        Args:
            updates: Итератор кортежей (new_status, path)
            
        Returns:
            Количество обновлённых записей
        """
        updates = list(updates)
        if not updates:
            return 0
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    f"UPDATE {self.files_table} SET status_sync = %s WHERE path = %s",
                    updates,
                )
                return cur.rowcount

    def reset_processed_to_added(self) -> int:
        """Сбрасывает зависшие 'processed' статусы в 'added'.
        
        Используется при запуске сервиса.
        
        Returns:
            Количество сброшенных записей
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    UPDATE {self.files_table}
                    SET status_sync = 'added', last_checked = CURRENT_TIMESTAMP
                    WHERE status_sync = 'processed'
                """)
                return cur.rowcount


__all__ = ["FileWatcherRepository", "FileStatus", "FileQueueItem"]
