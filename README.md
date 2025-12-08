
# ALPACA RAG

RAG-система обработки документов с микросервисной архитектурой.

## Архитектура

```
monitored_folder/ → FileWatcher → PostgreSQL+pgvector ← Ingest → Ollama (GPU)
                    (Сканер+API)    (files + chunks)    (Пайплайн) (LLM+Эмбеддинги)
                                          ↓
                                    Chat Backend → Ollama
                                    (RAG API)
```

### Сервисы

| Сервис | Порт | Описание |
|--------|------|----------|
| **filewatcher** | 8081 | Сканирует `monitored_folder`, API очереди файлов |
| **ingest** | — | Пайплайн: парсинг → очистка → чанкинг → метаданные → эмбеддинг |
| **chat-backend** | 8082 | RAG API: поиск по векторам + генерация ответов |
| **mcp-server** | 8083 | Model Context Protocol для внешних LLM-агентов |
| **admin-backend** | 8080 | Мониторинг системы |
| **unstructured** | 9000 | Парсинг документов с OCR |
| **ollama** | 11434 | LLM (qwen2.5:32b) и эмбеддинги (bge-m3) на GPU |

**Supabase** (PostgreSQL + pgvector) устанавливается отдельно в `~/supabase/docker`, порт **54322**.

### Поток обработки документов

1. **FileWatcher** сканирует `monitored_folder` → обновляет таблицу `files` (статусы: `added`/`updated`/`deleted`)
2. **Ingest** запрашивает `GET /api/next-file` у FileWatcher → помечает файл как `processed`
3. Пайплайн: **parsing** → **cleaning** → **chunking** → **metaextraction** → **embedding**
4. Чанки с векторами сохраняются в таблицу `chunks` → статус файла меняется на `ok` или `error`

### База данных

**Таблица `files`**: отслеживание файлов
- `file_path`, `file_hash` (SHA256), `status_sync` (`ok`/`added`/`updated`/`deleted`/`processed`/`error`)

**Таблица `chunks`**: векторное хранилище (pgvector)
- `content` (текст), `embedding` (vector 1024), `metadata` (JSONB: file_hash, file_path, title, summary, keywords, category, entities)

## Быстрый старт

### 1. Supabase (отдельно)

```bash
cd ~/supabase/docker
docker compose up -d
# Dashboard: http://localhost:8000, PostgreSQL: localhost:54322
```

### 2. Ollama (если локально с GPU)

```bash
cd ~/alpaca/services
docker compose -f docker-compose.yml -f ../scripts/setup_ollama/docker-compose.ollama.yml up -d ollama
```

Или укажите внешний Ollama: `export OLLAMA_BASE_URL=http://server-ip:11434`

### 3. Сервисы

```bash
cd ~/alpaca/services
docker compose up -d
```

### Проверка

```bash
curl http://localhost:8081/health   # FileWatcher
curl http://localhost:8082/health   # Chat Backend
curl http://localhost:11434/api/tags # Ollama
```

## Структура проекта

```
services/
├── docker-compose.yml        # Все сервисы
├── file_watcher/src/         # Сканер файлов + REST API
├── ingest/src/
│   ├── parsers/              # Word, PDF, PPTX, XLS, TXT
│   ├── cleaners/             # simple, stamps
│   ├── chunkers/             # simple, smart
│   ├── metaextractors/       # base, llm
│   ├── embedders/            # ollama
│   └── pipeline/             # Оркестрация
├── chat_backend/src/
│   ├── pipelines/            # RAG pipeline
│   ├── vector_searchers/     # pgvector
│   └── llm/                  # ollama
├── mcp_server/src/           # MCP протокол
└── admin_backend/src/        # Мониторинг
```

## Конфигурация

Все настройки через ENV в `docker-compose.yml`. Ключевые:

```yaml
# Ingest
CLEANER_PIPELINE: ["simple","stamps"]
CHUNKER_BACKEND: smart
METAEXTRACTOR_PIPELINE: ["base","llm"]

# Chat Backend
PIPELINE_TYPE: simple
RAG_TOP_K: 5
CHAT_BACKEND: agent  # simple | agent
```

## Внешний доступ

API доступен через reverse SSH tunnel на VDS:
- **Chat**: `https://api.alpaca-smart.com:8443/chat/`
- **Admin**: `https://api.alpaca-smart.com:8443/admin/`

## Полезные команды

```bash
# Логи сервиса
docker compose logs -f ingest

# Статистика файлов
psql $DATABASE_URL -c "SELECT status_sync, COUNT(*) FROM files GROUP BY status_sync;"

# Количество чанков
psql $DATABASE_URL -c "SELECT COUNT(*) FROM chunks;"

# Остановка
docker compose down
```

## Документация

- [.github/copilot-instructions.md](.github/copilot-instructions.md) — полное техническое описание для AI-ассистентов
- [docs/TODO.md](docs/TODO.md) — текущие задачи
