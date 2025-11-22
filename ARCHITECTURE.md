# Архитектура ALPACA RAG

> Документация архитектуры монолитной RAG системы версии 2.0.0

## 📋 Содержание

- [Обзор](#обзор)
- [Архитектурные решения](#архитектурные-решения)
- [Компоненты системы](#компоненты-системы)
- [Поток данных](#поток-данных)
- [База данных](#база-данных)
- [Масштабирование](#масштабирование)

---

## Обзор

ALPACA RAG - это монолитная система для автоматической обработки документов и семантического поиска с использованием локальных LLM моделей.

### Ключевые принципы

1. **Монолитная архитектура** - единый процесс вместо микросервисов
2. **Локальные модели** - полная автономность, без внешних API
3. **Автоматизация** - минимум ручных действий
4. **Простота** - легко разрабатывать, отлаживать, деплоить

### Диаграмма архитектуры

```
┌─────────────────────────────────────────────────────────────┐
│                    ALPACA RAG (Python 3.12)                 │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ FastAPI      │  │ Background   │  │ Core Logic   │    │
│  │ REST API     │  │ Workers      │  │              │    │
│  │              │  │ (APScheduler)│  │ - Parser     │    │
│  │ - Documents  │  │              │  │ - Chunker    │    │
│  │ - Search     │  │ - File Watch │  │ - Embedder   │    │
│  │ - Admin      │  │ - Processing │  │ - RAG        │    │
│  │ - Health     │  │   Queue      │  │              │    │
│  └──────────────┘  └──────────────┘  └──────────────┘    │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐ │
│  │         Database Layer (asyncpg)                     │ │
│  │         Connection Pool                              │ │
│  └──────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            │
                ┌───────────┼───────────┐
                │           │           │
        ┌───────▼──────┐ ┌──▼───────┐ ┌▼──────────────┐
        │ Unstructured │ │  Ollama  │ │ PostgreSQL    │
        │     API      │ │   LLM    │ │ + pgvector    │
        │  (Docker)    │ │ (Docker) │ │  (Supabase)   │
        └──────────────┘ └──────────┘ └───────────────┘
```

---

## Архитектурные решения

### Почему монолит вместо микросервисов?

**Проблемы старой микросервисной архитектуры:**
- ❌ 5 отдельных сервисов - сложность координации
- ❌ Network overhead между сервисами
- ❌ Дублирование кода (database.py в каждом)
- ❌ Сложная отладка (распределённые логи)
- ❌ Избыточная сложность для проекта такого масштаба

**Преимущества монолита:**
- ✅ Единая кодовая база
- ✅ Простая отладка - весь stack trace виден
- ✅ Нет network latency
- ✅ Shared connection pool к БД
- ✅ Atomic transactions
- ✅ Проще деплой и масштабирование

### Почему venv вместо Docker для основного приложения?

**Преимущества:**
- ✅ Быстрая разработка с hot reload
- ✅ Прямой доступ к debugger
- ✅ Меньше overhead
- ✅ Проще настройка IDE

**Docker остаётся для:**
- Unstructured API (сложные зависимости)
- Ollama (GPU поддержка)
- Admin Backend (изоляция, Docker API)

### Почему отказались от N8N?

**Проблемы N8N:**
- ❌ Избыточная сложность для простых workflow
- ❌ Сложная отладка (UI вместо кода)
- ❌ Медленные итерации (нужно править через веб)
- ❌ Требует Redis для очередей

**Замена на Python:**
- ✅ Весь workflow в коде
- ✅ Простая отладка с breakpoints
- ✅ Версионирование в Git
- ✅ Unit-тестирование

---

## Компоненты системы

### 1. FastAPI Application (app/api/)

REST API эндпоинты для взаимодействия с системой.

**Модули:**
- `health.py` - healthchecks, статус системы
- `documents.py` - CRUD операции с документами
- `search.py` - векторный поиск и RAG
- `admin.py` - мониторинг и управление

**Технологии:**
- FastAPI для REST API
- Pydantic для валидации
- CORS middleware
- Async handlers

### 2. Core Business Logic (app/core/)

Основная бизнес-логика обработки документов.

**Модули:**

#### file_watcher.py
```python
# Сканирование файловой системы
- Рекурсивный обход MONITORED_PATH
- Вычисление SHA256 хэша
- Фильтрация по расширениям и размеру
- Синхронизация с file_state
```

#### parser.py
```python
# Парсинг документов через Unstructured API
- Поддержка PDF, DOCX, XLSX, PPTX, TXT
- hi_res стратегия с OCR
- Эвристики для markdown форматирования
- Обработка таблиц и изображений
```

#### chunker.py
```python
# Разбиение текста на чанки
- RecursiveCharacterTextSplitter
- CHUNK_SIZE = 1000 символов
- CHUNK_OVERLAP = 200 символов
- Сохранение метаданных позиции
```

#### embedder.py
```python
# Генерация векторных представлений
- Интеграция с Ollama API
- Модель bge-m3 (размерность 1024)
- Батчинг запросов
- Retry логика при ошибках
```

#### rag.py
```python
# Retrieval-Augmented Generation
- Векторный поиск по documents
- Формирование контекста из TOP_K чанков
- Генерация ответа через qwen2.5
- Фильтрация по SIMILARITY_THRESHOLD
```

### 3. Background Workers (app/workers/)

Фоновые задачи для автоматической обработки.

#### scheduler.py
```python
# APScheduler для периодических задач
- File watcher: каждые SCAN_INTERVAL секунд
- Queue processor: каждые 10 секунд
- Cleanup: раз в день (удаление устаревших)
```

#### file_processor.py
```python
# Обработка очереди файлов
- Берёт файлы со status_sync = 'added' | 'updated'
- Ограничение MAX_CONCURRENT_PROCESSING
- Полный цикл: parse → chunk → embed → save
- Обработка ошибок и retry
```

### 4. Database Layer (app/db/)

Работа с PostgreSQL через asyncpg.

#### connection.py
```python
# Connection pool
- asyncpg.create_pool()
- Размер pool: DB_POOL_SIZE
- Max overflow: DB_MAX_OVERFLOW
- Автоматический reconnect
```

#### models.py
```python
# Pydantic models
- FileState - метаданные файлов
- Document - векторные чанки
- SearchResult - результаты поиска
```

---

## Поток данных

### 1. Добавление нового документа

```
User кладёт файл в MONITORED_PATH
           │
           ▼
    File Watcher (каждые 20 сек)
           │
           ├─ Вычисляет SHA256 hash
           ├─ Проверяет в file_state
           └─ Если новый → INSERT status_sync='added'
           │
           ▼
    File Processor (каждые 10 сек)
           │
           ├─ SELECT WHERE status_sync IN ('added', 'updated')
           ├─ UPDATE status_sync='processed'
           │
           ▼
    Parser (Unstructured API)
           │
           ├─ POST /general/v0/general
           └─ Извлекает текст + структуру
           │
           ▼
    Chunker
           │
           ├─ RecursiveCharacterTextSplitter
           └─ Создаёт chunks (1000 chars, overlap 200)
           │
           ▼
    Embedder (Ollama bge-m3)
           │
           ├─ POST /api/embeddings
           └─ Генерирует vectors (1024 dim)
           │
           ▼
    Database
           │
           ├─ INSERT INTO documents (file_hash, chunk_text, embedding)
           └─ UPDATE file_state SET status_sync='ok'
```

### 2. Поиск и RAG

```
User запрос через API
           │
           ▼
    Embedder
           │
           └─ Генерирует embedding запроса
           │
           ▼
    Vector Search (pgvector)
           │
           ├─ SELECT ... ORDER BY embedding <=> query_embedding
           └─ Возвращает TOP_K чанков
           │
           ▼
    Context Builder
           │
           ├─ Объединяет чанки
           └─ Фильтрует по SIMILARITY_THRESHOLD
           │
           ▼
    LLM (Ollama qwen2.5)
           │
           ├─ POST /api/generate
           ├─ Prompt: вопрос + контекст
           └─ Генерирует ответ
           │
           ▼
    Response
           │
           └─ JSON: answer + sources + metadata
```

---

## База данных

### Схема

```sql
-- Метаданные файлов
CREATE TABLE file_state (
    id SERIAL PRIMARY KEY,
    file_path TEXT NOT NULL UNIQUE,
    file_size BIGINT NOT NULL,
    file_hash TEXT NOT NULL,
    file_mtime DOUBLE PRECISION,
    status_sync TEXT DEFAULT 'ok',
    last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для file_state
CREATE INDEX idx_file_hash ON file_state(file_hash);
CREATE INDEX idx_status_sync ON file_state(status_sync);
CREATE INDEX idx_last_checked ON file_state(last_checked);

-- Векторные чанки документов
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE documents (
    id BIGSERIAL PRIMARY KEY,
    file_hash TEXT NOT NULL,
    file_path TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding VECTOR(1024),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT unique_chunk UNIQUE (file_hash, chunk_index)
);

-- Индексы для documents
CREATE INDEX idx_documents_file_hash ON documents(file_hash);
CREATE INDEX idx_documents_file_path ON documents(file_path);
CREATE INDEX idx_documents_embedding ON documents 
    USING ivfflat (embedding vector_cosine_ops) 
    WITH (lists = 100);
```

### Статусная модель file_state

| Статус | Описание | Переход |
|--------|----------|---------|
| `ok` | Файл обработан успешно | → `updated` (при изменении) |
| `added` | Новый файл, ждёт обработки | → `processed` |
| `updated` | Файл изменён, требует переобработки | → `processed` |
| `processed` | В процессе обработки | → `ok` или `error` |
| `deleted` | Файл удалён с диска | (финальный) |
| `error` | Ошибка при обработке | → `updated` (retry) |

### Запросы

```sql
-- Статистика файлов
SELECT status_sync, COUNT(*) 
FROM file_state 
GROUP BY status_sync;

-- Очередь обработки
SELECT file_path, file_size, status_sync, last_checked
FROM file_state
WHERE status_sync IN ('added', 'updated')
ORDER BY last_checked ASC
LIMIT 10;

-- Векторный поиск
SELECT 
    chunk_text,
    file_path,
    1 - (embedding <=> $1::vector) AS similarity
FROM documents
WHERE 1 - (embedding <=> $1::vector) > 0.7
ORDER BY embedding <=> $1::vector
LIMIT 5;

-- Статистика документов
SELECT 
    COUNT(*) as total_chunks,
    COUNT(DISTINCT file_hash) as unique_files,
    SUM(length(chunk_text)) as total_chars
FROM documents;
```

---

## Масштабирование

### Вертикальное масштабирование

Увеличение ресурсов одного сервера:

```bash
# Больше uvicorn workers
uvicorn main:app --workers 8

# Больше параллельных обработок
MAX_CONCURRENT_PROCESSING=4

# Больше connection pool
DB_POOL_SIZE=20
```

### Горизонтальное масштабирование

При росте нагрузки можно разделить компоненты:

```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│ API Server  │  │ API Server  │  │ API Server  │
│  (worker 1) │  │  (worker 2) │  │  (worker 3) │
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       │                │                │
       └────────────────┼────────────────┘
                        │
              ┌─────────▼─────────┐
              │   Load Balancer   │
              └─────────┬─────────┘
                        │
       ┌────────────────┼────────────────┐
       │                │                │
┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐
│  Database   │  │   Ollama    │  │ Unstructured│
│  (Supabase) │  │  (GPU x2)   │  │   (scaled)  │
└─────────────┘  └─────────────┘  └─────────────┘
```

**Background workers:**
- Запустить на отдельном сервере
- Использовать флаг `--no-api` для запуска только workers
- Координация через БД (file_state таблица)

### Оптимизация производительности

**Database:**
```sql
-- Увеличить lists для ivfflat индекса
CREATE INDEX idx_documents_embedding ON documents 
    USING ivfflat (embedding vector_cosine_ops) 
    WITH (lists = 1000);

-- Vacuum для очистки
VACUUM ANALYZE documents;
```

**Ollama:**
```yaml
# docker-compose.yml
environment:
  - OLLAMA_NUM_PARALLEL=4
  - OLLAMA_MAX_QUEUE=20
  - OLLAMA_MAX_LOADED_MODELS=2
```

**Chunking:**
```python
# Параллельная обработка чанков
async def process_chunks_parallel(chunks, batch_size=10):
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i+batch_size]
        await asyncio.gather(*[embed(chunk) for chunk in batch])
```

---

## Безопасность

### API Authentication

```python
# settings.py
ADMIN_API_KEY = "secure-random-key"

# app/api/admin.py
def verify_api_key(api_key: str = Header(...)):
    if api_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=401)
```

### CORS

```python
# main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Rate Limiting

```python
from slowapi import Limiter

limiter = Limiter(key_func=get_remote_address)

@app.get("/api/search")
@limiter.limit("10/minute")
async def search(query: str):
    ...
```

---

## Мониторинг

### Healthchecks

```python
# app/api/health.py
@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "database": await check_db(),
        "ollama": await check_ollama(),
        "unstructured": await check_unstructured(),
        "disk_space": check_disk(),
    }
```

### Метрики

```python
# app/utils/metrics.py
from prometheus_client import Counter, Histogram

documents_processed = Counter('documents_processed_total', 'Total documents')
processing_duration = Histogram('processing_duration_seconds', 'Processing time')

@processing_duration.time()
async def process_document(file_path):
    ...
    documents_processed.inc()
```

### Логирование

```python
# app/utils/logging.py
import logging
from pythonjsonlogger import jsonlogger

handler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
handler.setFormatter(formatter)

logger = logging.getLogger()
logger.addHandler(handler)
logger.setLevel(settings.LOG_LEVEL)
```

---

## Миграция со старой архитектуры

См. [MIGRATION_PLAN.md](MIGRATION_PLAN.md) для подробного плана миграции с микросервисной архитектуры на монолит.

**Ключевые изменения:**
- N8N workflow → Python код в `app/workers/file_processor.py`
- 5 микросервисов → 1 монолитное приложение
- Docker контейнеры → venv для основного приложения
- Разрозненная конфигурация → `settings.py`

---

## Будущие улучшения

- [ ] Поддержка дополнительных форматов (HTML, Markdown, CSV)
- [ ] Web UI для мониторинга и поиска
- [ ] Поддержка нескольких языков (multi-language embeddings)
- [ ] Incremental updates (обновление только изменённых чанков)
- [ ] GraphQL API как альтернатива REST
- [ ] Distributed tracing (OpenTelemetry)
- [ ] A/B тестирование различных моделей
- [ ] Автоматическое масштабирование на Kubernetes

---

**Версия документа:** 2.0.0  
**Дата:** 22 ноября 2025
