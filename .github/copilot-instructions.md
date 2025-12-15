# ALPACA RAG - Руководство для AI-ассистентов

## Обзор архитектуры

ALPACA — это **RAG (Retrieval Augmented Generation) система обработки документов** с распределённой микросервисной архитектурой:

```
monitored_folder/ → FileWatcher → PostgreSQL+pgvector ← Ingest → Ollama (GPU)
                    (Сканер+API)    (files + chunks)    (Пайплайн) (LLM+Эмбеддинги)
                                          ↓
                                    Chat Backend → Ollama
                                    (RAG API)
```

### Docker-сервисы (services/docker-compose.yml)

| Сервис | Порт | Описание |
|--------|------|----------|
| **filewatcher** | 8081 | Сканирует `monitored_folder`, REST API для очереди файлов |
| **ingest** | — | Пайплайн обработки: парсинг → чанкинг → эмбеддинг |
| **chat-backend** | 8082 | RAG API для чата, поиск по векторам + генерация ответов |
| **mcp-server** | 8083 | Model Context Protocol сервер для внешних LLM-агентов |
| **admin-backend** | 8080 | Мониторинг и управление системой |
| **ollama** | 11434 | LLM (qwen2.5:32b) и эмбеддинги (bge-m3) на GPU (вынесен в отдельный compose) |
| **unstructured** | 9000 | Парсинг документов с OCR |

**Supabase** (PostgreSQL + pgvector) — отдельная установка:
- **Локально (Windows)**: `C:\supabase\docker`
- **На сервере**: `~/supabase/docker`
- **Доступ из Docker**: через имя контейнера `supabase-db:5432` (после подключения к сети `alpaca_alpaca_network`)

### Структура сервисов

```
services/
├── docker-compose.yml      # Все сервисы
├── file_watcher/           # Изолированный микросервис
│   └── src/
├── ingest/                 # Пайплайн обработки документов
│   └── src/
│       ├── parsers/        # Word, PDF, PPTX, XLS, TXT
│       ├── cleaners/       # simple, stamps (pipeline)
│       ├── chunkers/       # simple, smart
│       ├── embedders/      # ollama
│       ├── metaextractors/ # base, llm (pipeline)
│       └── pipeline/       # Оркестрация
├── chat_backend/           # RAG API
│   └── src/
│       ├── backends/       # simple (RAG+Ollama), agent (LangChain+MCP)
│       ├── api/            # FastAPI роуты
│       └── llm/            # ollama generate
├── mcp_server/             # Model Context Protocol
│   └── src/
│       ├── embedder.py     # ollama embeddings
│       ├── vector_searcher.py # pgvector
│       └── main.py         # FastAPI MCP endpoint
└── admin_backend/          # Мониторинг
    └── src/

### Схема базы данных

**Таблица `files`** (отслеживание файлов):
- `file_path` (уникальный), `file_hash` (SHA256), `file_size`, `file_mtime`
- `status_sync`: `ok` (синхронизирован), `added` (новый), `updated` (изменён), `deleted` (удалён), `processed` (в очереди), `error` (ошибка)
- `last_checked`: временная метка последнего обновления статуса

**Таблица `chunks`** (векторное хранилище с pgvector):
- `id` (serial primary key)
- `content` (text) — текст чанка
- `embedding` (vector(1024)) — вектор для bge-m3
- `metadata` (JSONB) — структурированные метаданные (см. ниже)
- Индексы: HNSW по embedding, GIN по metadata

**Структура metadata чанка:**
```json
{
  // === Идентификация ===
  "file_hash": "sha256...",           // SHA256 исходного файла
  "file_path": "folder/doc.docx",     // Путь относительно monitored_folder
  "chunk_index": 5,                   // Индекс чанка (0-based)
  "total_chunks": 42,                 // Всего чанков в документе
  
  // === Файловые метаданные (base_extractor) ===
  "extension": "docx",                // Расширение файла
  "modified_at": "2023-04-10T10:37:28", // Дата модификации файла ISO
  
  // === Семантические метаданные (llm_extractor) ===
  "title": "Договор подряда №123",    // Заголовок документа
  "summary": "Краткое описание...",   // 1-2 предложения
  "keywords": ["договор", "подряд"],  // До 5 ключевых слов
  "category": "Договор подряда",      // Категория (см. список ниже)
  "entities": [                       // До 5 сущностей
    {"type": "person", "name": "Иванов И.И.", "role": "Директор"},
    {"type": "company", "name": "ООО Рога", "role": "Заказчик"}
  ]
}
```

**Категории документов** (поле `category`):
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

### Пайплайн обработки (Ingest Service)

```
1. FileWatcher сканирует monitored_folder → обновляет таблицу files
2. Ingest опрашивает GET /api/next-file (приоритет: deleted > updated > added)
3. Ingest помечает файл как 'processed' для предотвращения дублирования
4. Пайплайн: parsing → cleaning → chunking → metaextraction → embedding → БД
5. При успехе: status_sync='ok', при ошибке: status_sync='error'
```

**Поток статусов**: `added`/`updated`/`deleted` → `processed` → `ok`/`error`

### Конфигурация пайплайнов (docker-compose.yml)

**Ingest Service:**
```yaml
environment:
  # Cleaner pipeline - последовательная обработка
  - ENABLE_CLEANER=true
  - CLEANER_PIPELINE=["simple","stamps"]
  
  # Chunker - выбор одного
  - CHUNKER_BACKEND=smart  # simple | smart
  - CHUNK_SIZE=1000
  - CHUNK_OVERLAP=200
  
  # MetaExtractor pipeline - последовательная обработка
  - ENABLE_METAEXTRACTOR=true
  - METAEXTRACTOR_PIPELINE=["base","llm"]
  - LLM_METAEXTRACTOR_PREVIEW_LENGTH=2000
```

**Chat Backend:**
```yaml
environment:
  - CHAT_BACKEND=agent  # simple (RAG+Ollama) | agent (LangChain+MCP)
  - PIPELINE_TYPE=simple  # Тип RAG pipeline для simple backend
  - RAG_TOP_K=5
  - RAG_SIMILARITY_THRESHOLD=0.3
  - MCP_SERVER_URL=http://mcp-server:8000  # Для agent backend
```

### Registry-паттерн для компонентов

Каждый модуль (`cleaners/`, `chunkers/`, `metaextractors/`, `pipelines/`) использует единый паттерн:

```python
# __init__.py
COMPONENTS = {"name": component_func}  # Реестр
def build_component() -> Component:    # Фабрика из settings
def get_component_pipeline(names: List[str]) -> Component:  # Для pipeline
```

**Добавление нового компонента:**
1. Создать файл `my_component.py` с функцией
2. Зарегистрировать в `__init__.py` → `COMPONENTS`
3. Добавить в ENV (docker-compose.yml)

## Система конфигурации

**Принцип**: Все настройки задаются через ENV в `docker-compose.yml` или `.env` файл. Файлы `settings.py` в сервисах только валидируют и типизируют ENV-переменные через pydantic-settings.

### Файл .env (services/.env)

Создаётся вручную на каждой машине, **НЕ коммитится в git**:

```bash
# Database - через Docker network (одинаково для ноутбука и сервера)
DATABASE_URL=postgresql://postgres:your-password@supabase-db:5432/postgres

# Ollama - на ноутбуке через Tailscale IP Alpaca, на сервере локально
OLLAMA_BASE_URL=http://100.68.201.91:11434  # Ноутбук (через Tailscale)
# OLLAMA_BASE_URL=http://localhost:11434    # Alpaca (локальный)

# Paths
MONITORED_FOLDER_PATH=/path/to/monitored_folder
TMP_MD_PATH=/path/to/tmp_md
```

### Обязательные ENV-переменные

Каждый сервис требует свой набор ENV. Без них сервис не запустится:

```yaml
# Общие для всех
DATABASE_URL: postgresql://...  # Supabase PostgreSQL
OLLAMA_BASE_URL: http://ollama:11434

# Ingest-специфичные
FILEWATCHER_URL: http://filewatcher:8081
CLEANER_PIPELINE: ["simple","stamps"]
METAEXTRACTOR_PIPELINE: ["base","llm"]
CHUNKER_BACKEND: smart

# Chat Backend-специфичные  
CHAT_BACKEND: agent  # simple | agent
PIPELINE_TYPE: simple
RAG_TOP_K: 5
MCP_SERVER_URL: http://mcp-server:8000
```

## Рабочие процессы разработки

### Окружения

| Окружение | Машина | Supabase | Ollama | Доступ |
|-----------|--------|----------|--------|--------|
| **Development** | Ноутбук (asus) | `supabase-db:5432` (Docker network) | `100.68.201.91:11434` (Alpaca через Tailscale) | localhost |
| **Production** | Alpaca (alpaca-phantom) | `supabase-db:5432` (Docker network) | `localhost:11434` | SSH / Tailscale |

### SSH доступ к серверам

```bash
# Alpaca через Tailscale (без пароля)
ssh alpaca

# VDS (без пароля)
ssh vds

# Выполнить команду удалённо
ssh alpaca "docker ps"
ssh alpaca "cd ~/alpaca/services && docker compose logs -f filewatcher"
```

### Docker-сети и Supabase

Supabase и ALPACA работают в **разных Docker Compose проектах**. Для связи контейнер `supabase-db` подключается к сети ALPACA:

```bash
# Выполняется при первом запуске и при деплое
docker network connect alpaca_alpaca_network supabase-db
```

После этого все сервисы обращаются к БД по имени `supabase-db:5432`.

```bash
# Подключить supabase-db к сети ALPACA (выполняется при деплое)
docker network connect alpaca_alpaca_network supabase-db
```

После этого контейнеры ALPACA могут обращаться к БД по имени `supabase-db:5432`.

### Запуск сервисов

```bash
# 1. Запустить Supabase (отдельно)
cd ~/supabase/docker && docker compose up -d

# 2. Запустить Ollama (если локально с GPU)
cd ~/alpaca/services && docker compose -f docker-compose.yml -f ../scripts/setup_ollama/docker-compose.ollama.yml up -d ollama
# Или указать внешний: export OLLAMA_BASE_URL=http://server-ip:11434

# 3. Запустить сервисы ALPACA
cd ~/alpaca/services && docker compose up -d
# Запускает: filewatcher, ingest, chat-backend, mcp-server, admin-backend, unstructured
```

### Порты сервисов

- **Supabase Dashboard**: http://localhost:8000
- **PostgreSQL**: через Docker network (`supabase-db:5432`)
- **Ollama**: http://localhost:11434
- **Unstructured**: http://localhost:9000
- **FileWatcher API**: http://localhost:8081
- **Chat Backend**: http://localhost:8082
- **MCP Server**: http://localhost:8083
- **Admin Backend**: http://localhost:8080


**Сброс зависших файлов в статусе 'processed'**:
- FileWatcher автоматически сбрасывает `processed→ok` при запуске
- Или вручную: `db.reset_processed_statuses()`

**Если GPU не используется Ollama**:
```bash
docker exec -it alpaca-ollama-1 nvidia-smi  # Проверить видимость GPU
# Убедитесь в наличии deploy.resources.reservations.devices в docker-compose.yml
```

## Паттерны и соглашения кода

### Структура микросервисов

Каждый сервис в `services/` — **изолированный** и содержит:
- `src/settings.py` — pydantic-settings, валидирует ENV
- `src/contracts.py` — типы и протоколы
- `src/repository.py` — работа с PostgreSQL
- `src/main.py` — точка входа, FastAPI или worker loop
- `requirements.txt` — зависимости сервиса
- `Dockerfile` — образ сервиса

**Ingest Service** (`services/ingest/src/`):
- `parsers/` — Word, PDF, PPTX, XLS, TXT парсеры
- `cleaners/` — simple, stamps (pipeline)
- `chunkers/` — simple, smart
- `metaextractors/` — base, llm (pipeline)
- `embedders/` — ollama
- `pipeline/` — оркестрация
- `worker.py` — poll loop для FileWatcher API

**Chat Backend** (`services/chat_backend/src/`):
- `backends/` — Registry с реализациями:
  - `simple/` — RAG pipeline + Ollama (embedder, searcher, pipeline, ollama)
  - `agent/` — LangChain Agent + MCP Server (langchain, mcp)
  - `protocol.py` — интерфейс ChatBackend
- `api/` — FastAPI роуты
- `llm/` — ollama generate (deprecated, используется backends/simple/ollama.py)

**MCP Server** (`services/mcp_server/src/`):
- `embedder.py` — ollama embeddings
- `vector_searcher.py` — pgvector поиск
- `main.py` — FastAPI + MCP tools (search_documents)

> **Добавление нового Chat Backend**: см. `services/chat_backend/src/backends/HOW_TO_ADD_BACKEND.md`

### Паттерн логирования

```python
from logging_config import setup_logging, get_logger

setup_logging()  # Вызвать один раз при старте сервиса (в main.py)
logger = get_logger("alpaca.component_name")

logger.info(f"✅ Успех | file={path} count={n}")
logger.error(f"❌ Ошибка | file={path} error={e}")
```

Используйте эмодзи-префиксы для визуального сканирования логов: 🍎 (старт), ✅ (успех), ❌ (ошибка), 📖 (парсинг), 🔪 (чанкинг), 🔮 (эмбеддинг). НЕ УВЛЕКАЕМСЯ ЭМОДЗИ! только ключевые события.

### Паттерны работы с базой данных

**Всегда используйте context manager**:
```python
with db.get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("...")  # Авто-коммит при успехе, откат при исключении
```

**Операции с хэшем файла**: Используйте `file_hash` (SHA256) как первичный ключ для чанков через JSONB-поле metadata:
```python
# Вставка чанка
metadata = {'file_hash': file_hash, 'file_path': path, 'chunk_index': idx}
cur.execute("INSERT INTO chunks (content, metadata, embedding) VALUES (%s, %s, %s::vector)",
            (text, psycopg2.extras.Json(metadata), embedding_str))

# Удаление чанков по хэшу
cur.execute("DELETE FROM chunks WHERE metadata->>'file_hash' = %s", (file_hash,))
```

### Управление конкурентностью

Worker использует **семафоры** для ограничения параллельных операций (настраивается через settings.py):
```python
# Семафоры инициализируются из settings
PARSE_SEMAPHORE = Semaphore(settings.WORKER_MAX_CONCURRENT_PARSING)
EMBED_SEMAPHORE = Semaphore(settings.WORKER_MAX_CONCURRENT_EMBEDDING)
LLM_SEMAPHORE = Semaphore(settings.WORKER_MAX_CONCURRENT_LLM)

with PARSE_SEMAPHORE:
    result = parser_word_old_task(file_info)
```

ThreadPoolExecutor управляет параллелизмом на уровне файлов (настройка `WORKER_MAX_CONCURRENT_FILES`).

### Обработка ошибок

**Функции пайплайна** возвращают пустое значение/ноль при ошибке и логируют детали:
```python
def parser_word_old_task(file_id: dict) -> str:
    try:
        # ... логика парсинга
        return parsed_text
    except Exception as e:
        logger.error(f"Не удалось распарсить | file={path} error={e}")
        db.mark_as_error(file_hash)
        return ""  # Пустая строка сигнализирует о неудаче
```

Worker проверяет возвращаемые значения и помечает файлы соответственно (статус `ok` или `error`).

### Паттерн FileID

Файлы идентифицируются кортежем hash+path:
```python
from pydantic import BaseModel

class FileID(BaseModel):
    hash: str  # SHA256
    path: str  # Относительно MONITORED_PATH
```


## Точки интеграции

### FileWatcher API

**GET /api/next-file** - Получить следующий файл из очереди (приоритет: deleted > updated > added)
- Возвращает 200 с FileResponse или 204 если очередь пуста
- Worker немедленно помечает полученный файл как `processed` во избежание дублирования

**GET /api/queue/stats** - Получить количество файлов по значениям status_sync

### Ollama API

**Эндпоинт эмбеддингов**:
```python
response = requests.post(
    f"{settings.OLLAMA_BASE_URL}/api/embeddings",
    json={"model": settings.OLLAMA_EMBEDDING_MODEL, "prompt": text},
    timeout=60
)
embedding = response.json()['embedding']  # Список из 1024 чисел для bge-m3
```

Держите модели загруженными с помощью `OLLAMA_KEEP_ALIVE=-1` в docker-compose.yml.

### Unstructured API

Парсит документы с поддержкой OCR:
```python
with open(full_path, 'rb') as f:
    response = requests.post(
        settings.UNSTRUCTURED_API_URL,
        files={'files': (filename, f)},
        data={'strategy': 'hi_res', 'languages': 'rus,eng'},
        timeout=300
    )
elements = response.json()  # Список элементов документа
```


## Особенности проекта

1. **Supabase отдельно** - Находится в `~/supabase/docker`, не является частью основного docker-compose.yml
2. **Docker network для БД** - `supabase-db` подключён к `alpaca_alpaca_network`, доступ по имени контейнера
3. **Все сервисы в Docker** - Включая Ingest (бывший Worker)
4. **Временные распарсенные файлы** - Сохраняются в `/home/alpaca/tmp_md` как .md для отладки/проверки
5. **Блокировка статусом** - Статус `processed` предотвращает состояние гонки при обработке очереди
6. **Русский язык** - Комментарии, логи, документация смешивают русский и английский; код/API на английском
7. **Изолированные микросервисы** - Все сервисы независимы, имеют собственные settings/repository

## Сетевая архитектура (Tailscale + VDS)

### Обзор инфраструктуры

Все машины объединены в единую сеть через **Tailscale VPN**:

```
┌─────────────────────────────────────────────────────────────────────┐
│                           ИНТЕРНЕТ                                  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  VDS (95.217.205.233)                                               │
│  Tailscale: 100.114.64.71                                           │
│  • nginx reverse proxy (HTTPS :8443)                                │
│  • Публичный домен: api.alpaca-smart.com                            │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ Tailscale
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Alpaca Server (alpaca-phantom)                                     │
│  Tailscale: 100.68.201.91                                           │
│  • Production: все микросервисы                                     │
│  • Ollama + GPU (RTX 3090)                                          │
│  • Supabase PostgreSQL                                              │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ Tailscale
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Ноутбук разработчика (asus)                                        │
│  Tailscale: 100.69.74.5                                             │
│  • Development: локальные сервисы                                   │
│  • Ollama на Alpaca через Tailscale                                 │
│  • Локальная Supabase                                               │
└─────────────────────────────────────────────────────────────────────┘
```

### Машины и их роли

| Машина | Tailscale IP | Внешний IP | Роль |
|--------|--------------|------------|------|
| **VDS** (87041server) | 100.114.64.71 | 95.217.205.233 | Публичный прокси, nginx, SSL |
| **Alpaca** (alpaca-phantom) | 100.68.201.91 | — | Production, Ollama GPU |
| **Ноутбук** (asus) | 100.69.74.5 | — | Development |
| **Lovable.dev** | — | — | Frontend (внешний сервис) |

### SSH доступ

Конфигурация `~/.ssh/config` на ноутбуке:
```
# VDS сервер (внешний IP, порт 2222)
Host vds
    HostName 95.217.205.233
    Port 2222
    User root

# Alpaca сервер через Tailscale
Host alpaca alpaca-phantom
    HostName 100.68.201.91
    User alpaca
    ForwardAgent yes
```

Команды:
```bash
ssh alpaca    # → Alpaca через Tailscale (без пароля)
ssh vds       # → VDS (без пароля)
```

### Конфигурация nginx на VDS

nginx проксирует запросы на Alpaca через Tailscale:

```nginx
# /etc/nginx/sites-available/api.alpaca-smart.com
upstream alpaca_admin {
    server 100.68.201.91:8080;  # Tailscale IP
}

upstream alpaca_chat {
    server 100.68.201.91:8082;
}

upstream alpaca_supabase {
    server 100.68.201.91:8000;
}

server {
    listen 8443 ssl;
    server_name api.alpaca-smart.com;
    
    ssl_certificate /etc/letsencrypt/live/api.alpaca-smart.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.alpaca-smart.com/privkey.pem;
    
    location /chat/ {
        proxy_pass http://alpaca_chat/;
        # ... headers
    }
    
    location /admin/ {
        proxy_pass http://alpaca_admin/;
    }
    
    location /supabase/ {
        proxy_pass http://alpaca_supabase/;
    }
}
```

### URL-адреса API

**Production (через VDS):**
- **Admin Backend**: `https://api.alpaca-smart.com:8443/admin/`
- **Chat Backend**: `https://api.alpaca-smart.com:8443/chat/`
- **Supabase Studio**: `https://api.alpaca-smart.com:8444/`

**Development (локально на ноутбуке):**
- **Admin Backend**: `http://localhost:8080`
- **Chat Backend**: `http://localhost:8082`
- **Supabase Studio**: `http://localhost:8000`

### Docker-сети

**На Alpaca (production):**
- Сеть `alpaca_alpaca_network` объединяет все сервисы
- `supabase-db` подключён к этой сети: `docker network connect alpaca_alpaca_network supabase-db`
- DATABASE_URL использует `supabase-db:5432`

**На ноутбуке (development):**
- Сеть `alpaca_alpaca_network` для ALPACA сервисов
- `supabase-db` подключается к той же сети
- DATABASE_URL: `postgresql://...@supabase-db:5432/postgres`

### Файл .env для разных окружений

**Ноутбук** (`services/.env`):
```bash
# Database - через Docker network
DATABASE_URL=postgresql://postgres:PASSWORD@supabase-db:5432/postgres

# Ollama - на Alpaca через Tailscale
OLLAMA_BASE_URL=http://100.68.201.91:11434
```

**Alpaca** (`services/.env`):
```bash
# Database - через Docker network
DATABASE_URL=postgresql://postgres:PASSWORD@supabase-db:5432/postgres

# Ollama - локальный
OLLAMA_BASE_URL=http://localhost:11434
```

### ROOT_PATH для Swagger

При работе за reverse proxy с path-based routing:

```python
# В main.py сервиса
app = FastAPI(
    title="Service Name",
    root_path=os.getenv("ROOT_PATH", "")
)
```

```yaml
# В docker-compose.yml
environment:
  - ROOT_PATH=/chat  # или /admin
```

### Диагностика сети

```bash
# Проверить Tailscale статус
tailscale status

# Проверить доступность Alpaca
ssh alpaca "hostname && uptime"

# Проверить nginx на VDS
ssh vds "curl -s http://100.68.201.91:8082/health"

# Проверить production API
curl https://api.alpaca-smart.com:8443/chat/health
```

## Изоляция микросервисов

**Все сервисы** — полностью изолированные Docker-контейнеры:

- Каждый имеет собственные `settings.py`, `repository.py`, `requirements.txt`
- Не зависят от `core/`, `utils/`, корневого `settings.py`
- Могут развёртываться и обновляться независимо

**При изменении схемы БД** обновите SQL во всех репозиториях:
- `services/file_watcher/src/repository.py`
- `services/ingest/src/repository.py`
- `services/chat_backend/src/repository.py`
- `services/mcp_server/src/repository.py`
- `services/admin_backend/src/database.py`

## Развитие проекта

Текущий статус архитектуры:

1. **✅ Изоляция микросервисов** — все сервисы полностью изолированы, имеют собственные репозитории
2. **✅ Registry-паттерн** — компоненты пайплайна переключаются через ENV
3. **✅ Chat backends** — реализованы simple (RAG) и agent (LangChain+MCP)

## CI/CD

### GitHub Actions (.github/workflows/deploy.yml)

При push в `main` автоматически:
1. SSH на сервер `alpaca@alpaca-phantom`
2. `git pull` обновляет код
3. `docker compose build --no-cache` пересобирает образы
4. `docker compose up -d` перезапускает контейнеры
5. `docker network connect alpaca_alpaca_network supabase-db` — подключает БД к сети
6. Health checks всех сервисов

**Секреты GitHub** (Settings → Secrets):
- `SSH_PRIVATE_KEY` — приватный ключ для доступа к серверу
- `SSH_KNOWN_HOSTS` — fingerprint сервера

**Ручной деплой**:
```bash
ssh alpaca@alpaca-phantom "cd ~/alpaca && git pull && cd services && docker compose up -d --build"
```

## Полезные команды

```bash
# Управление сервисами
./scripts/start_services.sh  # Запустить все Docker-сервисы
./scripts/stop_services.sh   # Остановить все сервисы

# Проверить модели Ollama
curl http://localhost:11434/api/tags

# Проверить использование GPU
nvidia-smi

# Просмотреть статусы файлов
psql $DATABASE_URL -c "SELECT status_sync, COUNT(*) FROM files GROUP BY status_sync;"

# Проверить чанки
psql $DATABASE_URL -c "SELECT COUNT(*), COUNT(DISTINCT metadata->>'file_hash') FROM chunks;"

# Запустить тесты сервиса
cd services/ingest && python -m pytest tests/ -v
cd services/chat_backend && python -m pytest tests/ -v
cd services/file_watcher && python run_tests.sh
```

## При внесении изменений

- **Добавление настроек**: Только через ENV в `docker-compose.yml`, валидация в `settings.py` сервиса
- **Изменения БД**: Обновите файлы схем в `scripts/setup_supabase/` и repository во всех сервисах
- **Новые зависимости**: Добавьте в `requirements.txt` конкретного сервиса
- **Изменения Docker-сервисов**: Отредактируйте `services/docker-compose.yml`
- **Новый компонент пайплайна**: Создайте файл, зарегистрируйте в `__init__.py`, добавьте ENV

## Общение рекомендации
- Отвечайте на русском языке, если не указано иное
- Соблюдайте стиль кода проекта
