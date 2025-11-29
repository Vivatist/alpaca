import psycopg2.extras

from utils.chunk_manager import ChunkManager
from utils.file_manager import File


def test_delete_chunks_fallback_by_path(test_db):
    chunk_manager = ChunkManager(test_db)
    test_path = "/tmp/test_chunk_fallback.txt"
    legacy_hash = "legacy_hash_123"
    current_hash = "current_hash_456"

    file = File(
        path=test_path,
        hash=current_hash,
        status_sync="updated",
        size=1024,
    )

    with test_db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO files (path, size, hash, status_sync, last_checked)
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (path) DO UPDATE
                SET hash = EXCLUDED.hash,
                    size = EXCLUDED.size,
                    status_sync = EXCLUDED.status_sync,
                    last_checked = CURRENT_TIMESTAMP
                """,
                (test_path, file.size, file.hash, file.status_sync),
            )

            metadata = {
                "file_hash": legacy_hash,
                "file_path": test_path,
                "chunk_index": 0,
                "total_chunks": 1,
            }
            cur.execute(
                """
                INSERT INTO chunks (content, metadata)
                VALUES (%s, %s)
                """,
                ("legacy chunk", psycopg2.extras.Json(metadata)),
            )

    deleted = chunk_manager.delete_chunks(file)

    assert deleted == 1
    assert not test_db.get_chunks_by_hash(legacy_hash)
