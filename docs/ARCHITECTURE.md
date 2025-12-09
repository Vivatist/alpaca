# Архитектура ALPACA RAG

## Обзор системы

ALPACA — это **RAG (Retrieval Augmented Generation) система** для обработки документов с распределённой микросервисной архитектурой.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              ЛОКАЛЬНАЯ МАШИНА                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  monitored_folder/    ──►  FileWatcher  ──►  PostgreSQL+pgvector           │
│  (документы)               (сканер)          (files + chunks)              │
│                                                   │                         │
│                                                   ▼                         │
│                            Ingest  ◄────────────────                       │
│                            (пайплайн обработки)                            │
│                                   │                                         │
│                                   ▼                                         │
│                            Chat Backend  ──►  RAG API                      │
│                            (поиск + генерация)                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Tailscale VPN
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           СЕРВЕР (GPU)                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Ollama  ──►  qwen2.5:32b (LLM, 22GB VRAM)                                 │
│          ──►  bge-m3 (эмбеддинги, 1.6GB VRAM)                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Компоненты системы

### Docker-сервисы (services/docker-compose.yml)

| Сервис | Порт | Описание |
|--------|------|----------|
| **filewatcher** | 8081 | Сканирует `monitored_folder`, REST API для очереди файлов |
| **ingest** | — | Пайплайн обработки: парсинг → чанкинг → эмбеддинг |
| **chat-backend** | 8082 | RAG API для чата, поиск по векторам + генерация ответов |
| **mcp-server** | 8083 | Model Context Protocol сервер для внешних LLM-агентов |
| **admin-backend** | 8080 | Мониторинг и управление системой |
| **unstructured** | 9000 | Парсинг документов с OCR |

### Внешние зависимости

| Компонент | Расположение | Описание |
|-----------|--------------|----------|
| **Supabase** | Локально (`~/supabase/docker`) | PostgreSQL + pgvector, порт 54322 |
| **Ollama** | Сервер (Tailscale) | LLM и эмбеддинги на GPU |

## Поток данных

### 1. Индексация документов

```
┌──────────────┐    ┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│  Документ    │───►│ FileWatcher │───►│   Ingest     │───►│  PostgreSQL │
│  (.docx/.pdf)│    │  (очередь)  │    │  (пайплайн)  │    │  (chunks)   │
└──────────────┘    └─────────────┘    └──────────────┘    └─────────────┘
                                              │
                                              ▼
                                       ┌─────────────┐
                                       │   Ollama    │
                                       │ (эмбеддинги)│
                                       └─────────────┘
```

**Этапы пайплайна Ingest:**
1. **Parsing** — извлечение текста из документов (Word, PDF, PPTX, XLS)
2. **Cleaning** — очистка текста (удаление мусора, штампов)
3. **Chunking** — разбиение на смысловые блоки
4. **MetaExtraction** — извлечение метаданных (заголовок, категория, сущности)
5. **Embedding** — векторизация через Ollama (bge-m3)
6. **Storage** — сохранение в PostgreSQL с pgvector

### 2. RAG-запрос (чат)

**Simple backend** — классический RAG:

```
┌──────────────┐    ┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│   Вопрос     │───►│ Chat Backend│───►│  PostgreSQL  │───►│  Релевантные│
│   юзера      │    │ (эмбеддинг) │    │ (vector search)   │   чанки     │
└──────────────┘    └─────────────┘    └──────────────┘    └─────────────┘
                          │                                       │
                          ▼                                       │
                   ┌─────────────┐                                │
                   │   Ollama    │◄────────────────────────────────
                   │ (генерация) │
                   └─────────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │   Ответ     │
                   │  (stream)   │
                   └─────────────┘
```

**Agent backend** — LangChain Agent с MCP tools:

```
┌──────────────┐    ┌─────────────┐    ┌─────────────┐
│   Вопрос     │───►│ Chat Backend│───►│   Ollama    │
│   юзера      │    │ (LangChain) │    │  (Agent)    │
└──────────────┘    └─────────────┘    └─────────────┘
                          │                   │
                          │                   │ tool_call: search_documents
                          │                   ▼
                          │            ┌─────────────┐    ┌──────────────┐
                          │            │ MCP Server  │───►│  PostgreSQL  │
                          │            │  (tools)    │    │(vector search)│
                          │            └─────────────┘    └──────────────┘
                          │                   │
                          │                   │ результаты поиска
                          │                   ▼
                          │            ┌─────────────┐
                          │            │   Ollama    │
                          │            │ (генерация) │
                          │            └─────────────┘
                          │                   │
                          ▼                   ▼
                   ┌─────────────────────────────┐
                   │   Ответ (SSE stream)        │
                   │   + tool_calls + sources    │
                   └─────────────────────────────┘
```

**Преимущества Agent backend:**
- LLM сам решает, когда искать документы
- Может уточнять запрос и делать несколько поисков
- Возвращает информацию о вызовах инструментов
- Расширяемость через MCP протокол

## Схема базы данных

### Таблица `files`

Отслеживание состояния файлов в `monitored_folder`:

| Поле | Тип | Описание |
|------|-----|----------|
| `file_path` | VARCHAR | Уникальный путь файла |
| `file_hash` | VARCHAR | SHA256 хэш содержимого |
| `file_size` | BIGINT | Размер в байтах |
| `file_mtime` | TIMESTAMP | Время модификации |
| `status_sync` | VARCHAR | Статус: `ok`, `added`, `updated`, `deleted`, `processed`, `error` |
| `last_checked` | TIMESTAMP | Последняя проверка |

### Таблица `chunks`

Векторное хранилище с pgvector:

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | SERIAL | Primary key |
| `content` | TEXT | Текст чанка |
| `embedding` | VECTOR(1024) | Вектор для bge-m3 |
| `metadata` | JSONB | Структурированные метаданные |

### Структура metadata чанка

```json
{
  "file_hash": "sha256...",
  "file_path": "folder/doc.docx",
  "chunk_index": 5,
  "total_chunks": 42,
  
  "extension": "docx",
  "modified_at": "2023-04-10T10:37:28",
  
  "title": "Договор подряда №123",
  "summary": "Краткое описание...",
  "keywords": ["договор", "подряд"],
  "category": "Договор подряда",
  "entities": [
    {"type": "person", "name": "Иванов И.И.", "role": "Директор"},
    {"type": "company", "name": "ООО Рога", "role": "Заказчик"}
  ]
}
```

### Категории документов

1. Договор подряда
2. Договор купли-продажи
3. Трудовой договор
4. Протокол, меморандум
5. Доверенность
6. Акт выполненных работ
7. Счет-фактура, счет
8. Техническая документация
9. Презентация
10. Письмо
11. Бухгалтерская документация
12. Инструкция, регламент
13. Статья, публикация, книга
14. Прочее

## Структура кода

```
services/
├── docker-compose.yml          # Все сервисы ALPACA
│
├── file_watcher/               # Микросервис сканирования
│   └── src/
│       ├── main.py             # FastAPI приложение
│       ├── scanner.py          # Сканер файловой системы
│       └── repository.py       # Работа с БД
│
├── ingest/                     # Пайплайн обработки
│   └── src/
│       ├── parsers/            # Word, PDF, PPTX, XLS, TXT
│       ├── cleaners/           # simple, stamps
│       ├── chunkers/           # simple, smart
│       ├── metaextractors/     # base, llm
│       ├── embedders/          # ollama
│       └── pipeline/           # Оркестрация
│
├── chat_backend/               # RAG API
│   └── src/
│       ├── backends/           # simple (RAG), agent (LangChain+MCP)
│       ├── api/                # FastAPI роуты
│       └── llm/                # Ollama generate
│
├── mcp_server/                 # Model Context Protocol
│   └── src/
│       ├── embedder.py         # Ollama embeddings
│       ├── vector_searcher.py  # pgvector поиск
│       └── main.py             # FastAPI + MCP tools
│
└── admin_backend/              # Мониторинг
    └── src/
        ├── main.py             # FastAPI приложение
        └── database.py         # Статистика БД
```

## Паттерны проектирования

### Registry-паттерн для компонентов

Каждый модуль пайплайна использует единый паттерн:

```python
# __init__.py
COMPONENTS = {"name": component_func}  # Реестр компонентов
def build_component() -> Component:    # Фабрика из settings
def get_component_pipeline(names: List[str]) -> Component:  # Для pipeline
```

**Добавление нового компонента:**
1. Создать файл `my_component.py` с функцией
2. Зарегистрировать в `__init__.py` → `COMPONENTS`
3. Добавить в ENV (docker-compose.yml)

### Изоляция микросервисов

Каждый сервис — **полностью изолированный** Docker-контейнер:

- Собственные `settings.py`, `repository.py`, `requirements.txt`
- Не зависит от общих модулей (`core/`, `utils/`)
- Может развёртываться независимо

### Конфигурация через ENV

Все настройки задаются через переменные окружения в `docker-compose.yml`. Файлы `settings.py` только валидируют и типизируют их через pydantic-settings.

## Конфигурация пайплайнов

### Ingest Service

```yaml
environment:
  # Cleaner pipeline - последовательная обработка
  - ENABLE_CLEANER=true
  - CLEANER_PIPELINE=["simple","stamps"]
  
  # Chunker - выбор одного
  - CHUNKER_BACKEND=smart  # simple | smart
  - CHUNK_SIZE=1000
  - CHUNK_OVERLAP=200
  
  # MetaExtractor pipeline
  - ENABLE_METAEXTRACTOR=true
  - METAEXTRACTOR_PIPELINE=["base","llm"]
```

### Chat Backend

```yaml
environment:
  - CHAT_BACKEND=agent     # simple (RAG+Ollama) | agent (LangChain+MCP)
  - RAG_TOP_K=5            # Количество релевантных чанков
  - RAG_SIMILARITY_THRESHOLD=0.3
```

## Сетевая архитектура

### Локальная разработка

```
┌─────────────────────────────────────────────────────┐
│                   Docker Network                     │
│                  (alpaca_network)                    │
├─────────────────────────────────────────────────────┤
│  filewatcher ──► 8081                               │
│  ingest (internal)                                  │
│  chat-backend ──► 8082                              │
│  mcp-server ──► 8083                                │
│  admin-backend ──► 8080                             │
│  unstructured ──► 9000                              │
│                                                     │
│  supabase-db ──► 54322 (PostgreSQL)                 │
│  supabase-studio ──► 8000 (Dashboard)               │
└─────────────────────────────────────────────────────┘
          │
          │ 172.17.0.1 (Docker bridge)
          ▼
┌─────────────────────────────────────────────────────┐
│                  Host Machine                        │
└─────────────────────────────────────────────────────┘
          │
          │ Tailscale (100.68.201.91)
          ▼
┌─────────────────────────────────────────────────────┐
│                 GPU Server                           │
│                                                     │
│  Ollama ──► 11434                                   │
└─────────────────────────────────────────────────────┘
```

### Production (сервер)

```
┌─────────────────────────────────────────────────────┐
│                    ИНТЕРНЕТ                          │
└─────────────────────────────────────────────────────┘
          │
          │ HTTPS :8443
          ▼
┌─────────────────────────────────────────────────────┐
│           VDS (api.alpaca-smart.com)                │
│                                                     │
│  nginx (reverse proxy)                              │
│    /admin/ ──► SSH tunnel ──► 8080                  │
│    /chat/  ──► SSH tunnel ──► 8082                  │
└─────────────────────────────────────────────────────┘
          │
          │ SSH tunnel (autossh)
          ▼
┌─────────────────────────────────────────────────────┐
│              GPU Server (за NAT)                    │
│                                                     │
│  ALPACA services (Docker)                           │
│  Supabase (Docker)                                  │
│  Ollama (Docker, GPU)                               │
└─────────────────────────────────────────────────────┘
```

## API Endpoints

### Admin Backend (8080)

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/health` | GET | Health check |
| `/api/files/stats` | GET | Статистика файлов |
| `/api/files/list` | GET | Список файлов |
| `/api/files/queue` | GET | Очередь обработки |
| `/api/chunks/stats` | GET | Статистика чанков |
| `/api/dashboard` | GET | Данные для дашборда |

### FileWatcher (8081)

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/health` | GET | Health check |
| `/api/next-file` | GET | Следующий файл из очереди |
| `/api/queue/stats` | GET | Статистика очереди |

### Chat Backend (8082)

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/health` | GET | Health check |
| `/api/chat` | POST | RAG чат (SSE stream) |
| `/api/chat/stats` | GET | Статистика чата |
| `/api/chat/backends` | GET | Доступные backends |
| `/api/files/download` | GET | Скачать файл |
| `/api/files/preview` | GET | Превью файла |

### MCP Server (8083)

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/mcp` | POST | MCP protocol endpoint |
| `/docs` | GET | Swagger документация |

## Модели Ollama

| Модель | Назначение | VRAM | Параметры |
|--------|------------|------|-----------|
| **qwen2.5:32b** | Генерация ответов | 22 GB | 32B параметров |
| **bge-m3** | Эмбеддинги | 1.6 GB | 1024 размерность вектора |

Конфигурация:
- `OLLAMA_KEEP_ALIVE=-1` — держать модели загруженными
- `OLLAMA_NUM_PARALLEL=4` — параллельные запросы
