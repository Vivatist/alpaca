# Infrastructure

Инфраструктурный слой — **адаптеры** к внешним системам (базы данных, API, файловая система).

## Структура

```
infrastructure/
└── database/
    ├── __init__.py
    └── postgres.py    # PostgresFileRepository
```

## Компоненты

### PostgresFileRepository

Реализация интерфейса `FileRepository` из `domain/files/` для PostgreSQL + pgvector.

**Работает с двумя таблицами:**

| Таблица | Назначение |
|---------|------------|
| `files` | Отслеживание файлов (path, hash, status_sync, raw_text) |
| `chunks` | Векторное хранилище (content, metadata, embedding) |

**Основные методы:**

```python
# Управление статусами файлов
mark_as_ok(file_hash)           # status_sync → 'ok'
mark_as_error(file_hash)        # status_sync → 'error'
mark_as_processed(file_hash)    # status_sync → 'processed'

# Работа с чанками
save_chunks(file, chunks, embeddings)  # Сохранить чанки с эмбеддингами
delete_chunks_by_hash(file_hash)       # Удалить чанки файла

# Очередь обработки
get_next_file()                 # Получить следующий файл из очереди
get_queue_stats()               # Статистика по статусам

# Синхронизация
sync_filesystem_snapshot(files) # Синхронизировать с файловой системой
```

## Использование

```python
from core.infrastructure.database import PostgresFileRepository

# Создание репозитория
repo = PostgresFileRepository(
    database_url="postgresql://user:pass@localhost:54322/postgres",
    files_table="files",
    chunks_table="chunks"
)

# Context manager для транзакций
with repo.get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM files")
```

## Принципы

- **Реализует контракт из domain/** — `FileRepository`
- **Изолирует SQL** — бизнес-логика не знает о PostgreSQL
- **Автоматическое создание таблиц** — `_ensure_tables()` при инициализации
- **Направленность**: `domain ← application ← infrastructure`

## Расширение

Для добавления нового адаптера (например, SQLite или MongoDB):

1. Создайте новый файл в `database/` (например, `sqlite.py`)
2. Реализуйте интерфейс `FileRepository`
3. Экспортируйте в `__init__.py`
4. Подключите в `bootstrap.py` через настройку
