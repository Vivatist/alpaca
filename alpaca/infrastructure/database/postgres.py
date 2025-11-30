from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Dict, List, Iterable, Optional, Any

import psycopg2
import psycopg2.extras

from alpaca.domain.files import FileStatus, FileID, FileQueueItem
from alpaca.domain.files.repository import FileRepository
from utils.logging import get_logger

logger = get_logger("alpaca.infrastructure.postgres")


class PostgresFileRepository(FileRepository):
    """PostgreSQL implementation shared across services."""

    def __init__(
        self,
        database_url: Optional[str] = None,
        *,
        files_table: Optional[str] = None,
        chunks_table: str = "chunks",
        table_name: Optional[str] = None,
    ):
        conn_str = database_url or os.getenv("DATABASE_URL")
        super().__init__(conn_str)
        self.files_table = files_table or table_name or "files"
        self.chunks_table = chunks_table
        self._ensure_tables()

    # Backwards-compatible attribute access
    @property
    def table_name(self) -> str:
        return self.files_table

    @contextmanager
    def get_connection(self):  # type: ignore[override]
        conn = psycopg2.connect(self.connection_string)
        try:
            yield conn
            conn.commit()
        except Exception as exc:  # pragma: no cover - network failures
            conn.rollback()
            logger.error(f"Database error: {exc}")
            raise
        finally:
            conn.close()

    # --- Schema helpers ---------------------------------------------------------
    def _ensure_tables(self) -> None:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
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
                    """
                )
                cur.execute(
                    f"""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='{self.files_table}' AND column_name='hash') THEN
                            ALTER TABLE {self.files_table} ADD COLUMN hash TEXT;
                        END IF;
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='{self.files_table}' AND column_name='mtime') THEN
                            ALTER TABLE {self.files_table} ADD COLUMN mtime DOUBLE PRECISION;
                        END IF;
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='{self.files_table}' AND column_name='status_sync') THEN
                            ALTER TABLE {self.files_table} ADD COLUMN status_sync TEXT DEFAULT 'ok';
                        END IF;
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='{self.files_table}' AND column_name='raw_text') THEN
                            ALTER TABLE {self.files_table} ADD COLUMN raw_text TEXT;
                        END IF;
                    END $$;
                    """
                )
                cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.files_table}_path ON {self.files_table}(path)")
                cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.files_table}_hash ON {self.files_table}(hash)")
                cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{self.files_table}_status_sync ON {self.files_table}(status_sync)")

    # --- Queue helpers ----------------------------------------------------------
    def _decide_action_for_existing_file(self, current_status: Optional[str], hash_matches: bool) -> tuple[str, Optional[str]]:
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

    # --- File watcher specific flows -------------------------------------------
    def sync_by_hash(self, disk_files: List[Dict[str, Any]]) -> Dict[str, int]:
        stats = {"added": 0, "updated": 0, "unchanged": 0, "deleted": 0}
        from psycopg2.extras import execute_values

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT path, hash, status_sync FROM {self.files_table}"
                )
                db_records = {row[0]: {"hash": row[1], "status": row[2]} for row in cur.fetchall()}
                disk_paths = {f["path"]: f for f in disk_files}

                inserts: List[tuple] = []
                status_updates: List[tuple] = []
                full_updates: List[tuple] = []

                for disk_path, disk_file in disk_paths.items():
                    if disk_path not in db_records:
                        inserts.append(
                            (
                                disk_path,
                                disk_file["size"],
                                disk_file["hash"],
                                disk_file["mtime"],
                            )
                        )
                        stats["added"] += 1
                        continue

                    db_record = db_records[disk_path]
                    hash_matches = db_record["hash"] == disk_file["hash"]
                    action, new_status = self._decide_action_for_existing_file(
                        db_record["status"], hash_matches
                    )

                    if action == "skip":
                        stats["unchanged"] += 1
                    elif action == "update_status" and new_status:
                        status_updates.append((new_status, disk_path))
                        stats["updated"] += 1
                    elif action == "update_full" and new_status:
                        full_updates.append(
                            (
                                disk_file["hash"],
                                disk_file["size"],
                                disk_file["mtime"],
                                new_status,
                                disk_path,
                            )
                        )
                        stats["updated"] += 1

                if inserts:
                    execute_values(
                        cur,
                        f"""
                        INSERT INTO {self.files_table} (path, size, hash, mtime, last_checked, status_sync)
                        VALUES %s
                        """,
                        inserts,
                        template="(%s, %s, %s, %s, CURRENT_TIMESTAMP, 'added')",
                        page_size=500,
                    )

                if status_updates:
                    cur.executemany(
                        f"""
                        UPDATE {self.files_table}
                        SET status_sync = %s, last_checked = CURRENT_TIMESTAMP
                        WHERE path = %s
                        """,
                        status_updates,
                    )

                if full_updates:
                    cur.executemany(
                        f"""
                        UPDATE {self.files_table}
                        SET hash = %s, size = %s, mtime = %s, status_sync = %s, last_checked = CURRENT_TIMESTAMP
                        WHERE path = %s
                        """,
                        full_updates,
                    )

                missing_paths = set(db_records.keys()) - set(disk_paths.keys())
                if missing_paths:
                    paths_to_delete = [
                        path
                        for path in missing_paths
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

    def get_file_state_records(self) -> List[tuple]:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT path, hash, status_sync FROM {self.files_table}"
                )
                return cur.fetchall()

    def get_documents_records(self) -> List[tuple]:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT metadata->>'file_hash' as hash,
                           metadata->>'file_path' as path,
                           COUNT(*)
                    FROM {self.chunks_table}
                    WHERE metadata->>'file_hash' IS NOT NULL
                      AND metadata->>'file_path' IS NOT NULL
                    GROUP BY metadata->>'file_hash', metadata->>'file_path'
                    """
                )
                return cur.fetchall()

    def update_status_sync_batch(self, updates: Iterable[tuple[str, str]]) -> int:
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

    def get_next_file_for_processing(self) -> Optional[FileQueueItem]:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT path, hash, size, status_sync, last_checked
                    FROM {self.files_table}
                    WHERE status_sync IN ('deleted', 'updated', 'added')
                    ORDER BY CASE status_sync
                        WHEN 'deleted' THEN 1
                        WHEN 'updated' THEN 2
                        WHEN 'added' THEN 3
                    END, last_checked ASC
                    LIMIT 1
                    """
                )
                row = cur.fetchone()
                if not row:
                    return None
                return FileQueueItem(
                    path=row[0],
                    hash=row[1],
                    size=row[2],
                    status=FileStatus(row[3]),
                    last_checked=row[4],
                )

    def get_queue_stats(self) -> Dict[str, int]:
        stats = {"deleted": 0, "updated": 0, "added": 0, "total": 0}
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT status_sync, COUNT(*)
                    FROM {self.files_table}
                    WHERE status_sync IN ('deleted', 'updated', 'added')
                    GROUP BY status_sync
                    """
                )
                for status, count in cur.fetchall():
                    stats[status] = count
                    stats["total"] += count
        return stats

    # --- Worker helpers ---------------------------------------------------------
    def get_processed_count(self) -> int:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT COUNT(*) FROM {self.files_table} WHERE status_sync = 'processed'"
                )
                return cur.fetchone()[0]

    def get_pending_files(self) -> Dict[str, List[FileID]]:
        result = {"added": [], "updated": [], "deleted": []}
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT path, hash, size, status_sync
                    FROM {self.files_table}
                    WHERE status_sync IN ('added', 'updated', 'deleted')
                    ORDER BY mtime DESC
                    """
                )
                for path, file_hash, *_rest, status in cur.fetchall():
                    file_id = FileID(hash=file_hash, path=path)
                    result[status].append(file_id)
        return result

    def mark_as_processed(self, file_hash: str) -> bool:
        return self._update_status(file_hash, FileStatus.PROCESSED)

    def mark_as_ok(self, file_hash: str) -> bool:
        return self._update_status(file_hash, FileStatus.OK)

    def mark_as_error(self, file_hash: str) -> bool:
        return self._update_status(file_hash, FileStatus.ERROR)

    def _update_status(self, file_hash: str, status: FileStatus) -> bool:
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

    def reset_processed_to_status(self, target_status: FileStatus = FileStatus.ADDED) -> int:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE {self.files_table}
                    SET status_sync = %s
                    WHERE status_sync = 'processed'
                    """,
                    (target_status.value,),
                )
                return cur.rowcount

    # --- File + chunk maintenance ----------------------------------------------
    def delete_file_by_hash(self, file_hash: str) -> bool:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"DELETE FROM {self.files_table} WHERE hash = %s",
                    (file_hash,),
                )
                return cur.rowcount > 0

    def delete_chunks_by_hash(self, file_hash: str) -> int:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"DELETE FROM {self.chunks_table} WHERE metadata->>'file_hash' = %s",
                    (file_hash,),
                )
                return cur.rowcount

    def delete_chunks_by_path(self, file_path: str) -> int:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"DELETE FROM {self.chunks_table} WHERE metadata->>'file_path' = %s",
                    (file_path,),
                )
                return cur.rowcount

    def set_raw_text(self, file_hash: str, raw_text: str) -> bool:
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

    def get_chunks_by_hash(self, file_hash: str) -> List[tuple]:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT content, metadata, embedding
                    FROM {self.chunks_table}
                    WHERE metadata->>'file_hash' = %s
                    ORDER BY (metadata->>'chunk_index')::int
                    """,
                    (file_hash,),
                )
                return cur.fetchall()

    def save_chunk(self, content: str, metadata: dict, embedding: Optional[List[float]] = None) -> bool:
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
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT COUNT(*) FROM {self.chunks_table} WHERE metadata->>'file_hash' = %s",
                    (file_hash,),
                )
                return cur.fetchone()[0]


# Backwards-compatible alias -----------------------------------------------------
PostgreDataBase = PostgresFileRepository
