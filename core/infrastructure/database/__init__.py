"""
Инфраструктурные адаптеры для работы с базой данных.

=== НАЗНАЧЕНИЕ ===
Реализация интерфейса FileRepository для PostgreSQL + pgvector.
Инкапсулирует всю работу с БД:
- Таблица files (отслеживание файлов)
- Таблица chunks (векторы с pgvector)

=== ЭКСПОРТЫ ===
- PostgresFileRepository — реализация FileRepository/Database

=== ИСПОЛЬЗОВАНИЕ ===

    from core.infrastructure.database import PostgresFileRepository
    from core.domain.files import FileSnapshot

    # Создать репозиторий
    repo = PostgresFileRepository(
        database_url="postgresql://user:pass@localhost:54322/postgres",
        files_table="files"
    )

    # Работа с файлами
    file = FileSnapshot(path="doc.txt", hash="abc123", status_sync="added")
    repo.mark_as_ok(file)       # Пометить как успешно обработанный
    repo.mark_as_error(file)    # Пометить как ошибку
    repo.delete_chunks_by_hash(file.hash)  # Удалить чанки

    # Context manager для транзакций
    with repo.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM files")
            # Авто-commit при успехе, авто-rollback при ошибке

=== ТАБЛИЦЫ ===
files: hash (PK), path, size, mtime, status_sync, last_checked
chunks: id, content, metadata (JSONB), embedding (vector[1024])

=== ПОРТ БД ===
Supabase использует порт 54322 (не 5432!)
"""

from .postgres import PostgresFileRepository

__all__ = ["PostgresFileRepository"]
