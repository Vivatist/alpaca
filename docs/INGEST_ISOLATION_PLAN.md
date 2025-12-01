# План изоляции Ingest Service (Вариант А)

## Цель

Создать **полностью изолированный Docker-сервис** `ingest` со всем пайплайном обработки документов, без зависимости от `core/`.

## Целевая структура

```
services/
├── file_watcher/      # ✅ уже изолирован
├── admin_backend/     # ✅ уже изолирован  
├── ingest/            # 🆕 новый сервис
│   ├── Dockerfile
│   ├── requirements.txt
│   └── src/
│       ├── main.py           # Точка входа, сборка зависимостей
│       ├── config.py         # Настройки сервиса (из ENV)
│       ├── contracts.py      # Type aliases: Parser, Cleaner, Chunker, Embedder
│       ├── repository.py     # PostgreSQL + pgvector
│       ├── worker.py         # Цикл опроса FileWatcher API
│       ├── pipeline/
│       │   ├── __init__.py
│       │   ├── ingest.py     # IngestDocument use-case
│       │   └── process.py    # ProcessFileEvent (added/updated/deleted)
│       ├── parsers/
│       │   ├── __init__.py   # registry + get_parser()
│       │   ├── word.py       # WordParser (python-docx)
│       │   ├── pdf.py        # PDFParser (pdfplumber)
│       │   ├── txt.py        # TXTParser
│       │   ├── pptx.py       # PPTXParser (python-pptx)
│       │   └── xls.py        # XLSParser (openpyxl)
│       ├── cleaners/
│       │   ├── __init__.py   # get_cleaner()
│       │   └── simple.py     # SimpleCleaner
│       ├── chunkers/
│       │   ├── __init__.py   # get_chunker()
│       │   └── fixed_size.py # FixedSizeChunker
│       └── embedders/
│           ├── __init__.py   # get_embedder()
│           └── ollama.py     # OllamaEmbedder (HTTP к Ollama)
├── ollama/            # остаётся отдельным (GPU)
└── unstructured/      # остаётся отдельным (тяжёлый)
```

## Этапы реализации

### Этап 1: Создание структуры (30 мин)
- [ ] Создать `services/ingest/` директорию
- [ ] Создать `requirements.txt` с зависимостями
- [ ] Создать `Dockerfile`
- [ ] Создать `src/config.py` — настройки из ENV
- [ ] Создать `src/contracts.py` — все type aliases

### Этап 2: Repository (20 мин)
- [ ] Создать `src/repository.py` — PostgreSQL адаптер
  - `mark_as_ok()`, `mark_as_error()`, `mark_as_processed()`
  - `delete_chunks_by_hash()`, `save_chunk()`
  - `get_connection()` context manager

### Этап 3: Парсеры (40 мин)
- [ ] Скопировать и адаптировать из `core/application/document_processing/parsers/`:
  - `word.py` → `src/parsers/word.py`
  - `pdf.py` → `src/parsers/pdf.py`
  - `txt.py` → `src/parsers/txt.py`
  - `pptx.py` → `src/parsers/pptx.py`
  - `xls.py` → `src/parsers/xls.py`
- [ ] Создать `src/parsers/__init__.py` с registry

### Этап 4: Cleaners, Chunkers (20 мин)
- [ ] `src/cleaners/simple.py` — скопировать из `core/application/document_processing/cleaners/`
- [ ] `src/chunkers/fixed_size.py` — скопировать из `core/application/document_processing/chunkers/`
- [ ] Создать `__init__.py` с фабриками

### Этап 5: Embedder (20 мин)
- [ ] `src/embedders/ollama.py` — адаптировать `custom_embedder.py`
- [ ] Убрать зависимость от `core/domain/files/repository`
- [ ] Использовать локальный `repository.py`

### Этап 6: Pipeline (30 мин)
- [ ] `src/pipeline/ingest.py` — IngestDocument use-case
- [ ] `src/pipeline/process.py` — ProcessFileEvent (роутинг по статусу)
- [ ] Адаптировать логику из `core/application/processing/use_cases.py`

### Этап 7: Worker (20 мин)
- [ ] `src/worker.py` — цикл опроса FileWatcher API
- [ ] Адаптировать из `utils/worker.py`
- [ ] ThreadPoolExecutor для параллельной обработки

### Этап 8: Main и сборка (15 мин)
- [ ] `src/main.py` — точка входа
  - Инициализация repository
  - Сборка pipeline с зависимостями
  - Запуск worker
- [ ] Обновить `services/docker-compose.yml`

### Этап 9: Тестирование (30 мин)
- [ ] `docker compose build ingest`
- [ ] `docker compose up ingest`
- [ ] Проверить обработку файлов
- [ ] Проверить логи и статусы

### Этап 10: Cleanup (опционально)
- [ ] Удалить/архивировать `core/application/document_processing/`
- [ ] Обновить `main.py` в корне (или удалить)
- [ ] Обновить документацию

## Зависимости (requirements.txt)

```
# Web
requests>=2.31.0
httpx>=0.25.0

# Database
psycopg2-binary>=2.9.9

# Parsers
python-docx>=1.1.0
pdfplumber>=0.10.0
python-pptx>=0.6.23
openpyxl>=3.1.2

# Utils
pydantic>=2.5.0
pydantic-settings>=2.1.0
```

## Переменные окружения

```env
# Database
DATABASE_URL=postgresql://user:pass@host:port/db

# FileWatcher
FILEWATCHER_URL=http://filewatcher:8081

# Ollama
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_EMBEDDING_MODEL=bge-m3

# Worker
WORKER_POLL_INTERVAL=5
WORKER_MAX_CONCURRENT_FILES=5
WORKER_MAX_CONCURRENT_PARSING=2
WORKER_MAX_CONCURRENT_EMBEDDING=3

# Paths
MONITORED_PATH=/monitored_folder
TMP_MD_PATH=/tmp_md

# Features
ENABLE_CLEANER=true
```

## contracts.py (упрощённые контракты)

```python
"""Контракты Ingest Service"""
from dataclasses import dataclass
from typing import Callable, Protocol, List, Optional
from enum import Enum

@dataclass(frozen=True)
class FileSnapshot:
    hash: str
    path: str
    size: int = 0
    status_sync: str = "added"
    raw_text: str = ""

class SyncStatus(str, Enum):
    OK = "ok"
    ADDED = "added"
    UPDATED = "updated"
    DELETED = "deleted"
    PROCESSED = "processed"
    ERROR = "error"

# Component contracts
Parser = Callable[[FileSnapshot], str]
Cleaner = Callable[[str], str]
Chunker = Callable[[str], List[str]]
Embedder = Callable[["Repository", FileSnapshot, List[str]], int]

class Repository(Protocol):
    def mark_as_ok(self, file_hash: str) -> None: ...
    def mark_as_error(self, file_hash: str) -> None: ...
    def mark_as_processed(self, file_hash: str) -> None: ...
    def delete_chunks_by_hash(self, file_hash: str) -> int: ...
    def save_chunk(self, content: str, metadata: dict, embedding: List[float]) -> bool: ...
```

## Оценка времени

| Этап | Время |
|------|-------|
| 1. Структура | 30 мин |
| 2. Repository | 20 мин |
| 3. Парсеры | 40 мин |
| 4. Cleaners/Chunkers | 20 мин |
| 5. Embedder | 20 мин |
| 6. Pipeline | 30 мин |
| 7. Worker | 20 мин |
| 8. Main | 15 мин |
| 9. Тестирование | 30 мин |
| **Итого** | **~4 часа** |

## Риски и митигация

| Риск | Митигация |
|------|-----------|
| Дублирование кода | Осознанный trade-off ради изоляции |
| Расхождение логики | Тесты, единая документация |
| Сложность отладки в Docker | Volume для логов, `docker logs -f` |

## После изоляции

1. **core/** остаётся для будущего **RAG Query Service**
2. Или `core/` можно полностью удалить, сделав Query Service тоже изолированным в `services/query/`
3. `main.py` в корне становится не нужен

---

**Готов к реализации!**
