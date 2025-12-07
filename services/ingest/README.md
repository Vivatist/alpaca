# Ingest Service

Изолированный сервис обработки документов для ALPACA RAG системы.

## Возможности

- **Парсинг документов**: Word (.doc, .docx), PDF, Excel (.xls, .xlsx), PowerPoint (.ppt, .pptx), TXT
- **Очистка текста**: Pipeline клинеров (simple + stamps)
- **Извлечение метаданных**: Simple (расширение) или LLM (title, summary, keywords)
- **Чанкинг**: Simple или Smart (LangChain с overlap)
- **Эмбеддинг**: Ollama API с batch-обработкой
- **Хранение**: PostgreSQL + pgvector

## Архитектура

```
FileWatcher API → Worker → Pipeline → PostgreSQL
                    │
                    ├── 1. Parse (Word/PDF/Excel/PPT/TXT)
                    ├── 2. Clean (simple → stamps)
                    ├── 3. MetaExtract (simple/llm)
                    ├── 4. Chunk (simple/smart)
                    └── 5. Embed (Ollama)
```

## Переменные окружения

```env
# Database
DATABASE_URL=postgresql://user:pass@host:port/db

# Services
FILEWATCHER_URL=http://filewatcher:8081
OLLAMA_BASE_URL=http://ollama:11434
UNSTRUCTURED_API_URL=http://unstructured:8000/general/v0/general

# Models
OLLAMA_EMBEDDING_MODEL=bge-m3
OLLAMA_LLM_MODEL=qwen2.5:32b

# Worker
WORKER_POLL_INTERVAL=5
WORKER_MAX_CONCURRENT_FILES=5
WORKER_MAX_CONCURRENT_PARSING=2
WORKER_MAX_CONCURRENT_EMBEDDING=3

# Pipeline
ENABLE_CLEANER=true
CLEANER_PIPELINE=["simple","stamps"]
CHUNKER_BACKEND=smart
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
ENABLE_METAEXTRACTOR=true
METAEXTRACTOR_BACKEND=simple

# Paths
MONITORED_PATH=/monitored_folder
TMP_MD_PATH=/tmp_md

# Logging
LOG_LEVEL=INFO
```

## Cleaner Pipeline

Клинеры применяются последовательно:

1. **simple** - Базовая очистка:
   - Удаление управляющих символов
   - Нормализация Unicode пробелов
   - Удаление множественных пробелов и переносов

2. **stamps** - Удаление штампов:
   - Блоки "Прошито, пронумеровано"
   - Нормализация underscores (`\_\_\_` → `___`)

## Запуск

### Docker Compose

```bash
cd services
docker compose build ingest
docker compose up ingest
```

### Локально (для разработки)

```bash
cd services/ingest
pip install -r requirements.txt
python -m src.main
```

## Структура

```
services/ingest/
├── Dockerfile
├── requirements.txt
├── README.md
└── src/
    ├── main.py           # Точка входа
    ├── config.py         # Настройки из ENV
    ├── contracts.py      # Type aliases и Protocol'ы
    ├── repository.py     # PostgreSQL адаптер
    ├── worker.py         # Управление потоками
    ├── logging_config.py # Логирование
    ├── parsers/          # Парсеры документов
    │   ├── word.py
    │   ├── pdf.py
    │   ├── txt.py
    │   ├── pptx.py
    │   └── excel.py
    ├── cleaners/         # Клинеры текста
    ├── chunkers/         # Чанкеры
    ├── embedders/        # Эмбеддеры
    ├── metaextractors/   # Экстракторы метаданных
    └── pipeline/         # Use-cases
        ├── ingest.py     # IngestDocument
        └── process.py    # ProcessFileEvent
```

## Независимость от core/

Сервис полностью изолирован и не зависит от `core/`:
- Собственные контракты (`contracts.py`)
- Собственный репозиторий (`repository.py`)
- Копии парсеров без зависимостей от core
