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
| **ingest** | - | Пайплайн обработки: парсинг → чанкинг → эмбеддинг |
| **chat-backend** | 8082 | RAG API для чата, поиск по векторам + генерация ответов |
| **admin-backend** | 8080 | Мониторинг и управление системой |
| **ollama** | 11434 | LLM (qwen2.5:32b) и эмбеддинги (bge-m3) на GPU |
| **unstructured** | 9000 | Парсинг документов с OCR |

**Supabase** (PostgreSQL + pgvector) — отдельная установка в `~/supabase/docker`, порт 54322.

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
│       ├── pipelines/      # simple (расширяемый)
│       ├── embedders/      # ollama
│       ├── vector_searchers/ # pgvector
│       └── llm/            # ollama
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
  - PIPELINE_TYPE=simple  # Тип RAG pipeline
  - RAG_TOP_K=5
  - RAG_SIMILARITY_THRESHOLD=0.3
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

**Принцип**: Все настройки задаются через ENV в `docker-compose.yml`. Файлы `settings.py` в сервисах только валидируют и типизируют ENV-переменные через pydantic-settings.

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
PIPELINE_TYPE: simple
RAG_TOP_K: 5
```

## Рабочие процессы разработки

### Запуск сервисов

```bash
# 1. Запустить Supabase (отдельно, работает на порту 54322)
cd ~/supabase/docker && docker compose up -d

# 2. Запустить сервисы ALPACA (все в Docker)
cd ~/alpaca/services && docker compose up -d
# Запускает: filewatcher, ingest, chat-backend, admin-backend, ollama, unstructured
```

### Порты сервисов

- **Supabase Dashboard**: http://localhost:8000
- **PostgreSQL**: localhost:54322 (не 5432!)
- **Ollama**: http://localhost:11434
- **Unstructured**: http://localhost:9000
- **FileWatcher API**: http://localhost:8081
- **Chat Backend**: http://localhost:8082
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
- `pipelines/` — simple RAG pipeline (расширяемый)
- `embedders/` — ollama
- `vector_searchers/` — pgvector
- `llm/` — ollama generate
- `api/` — FastAPI роуты

### Паттерн логирования

```python
from utils.logging import setup_logging, get_logger

setup_logging()  # Вызвать один раз при входе в модуль
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
2. **Порт 54322, а не 5432** - Supabase PostgreSQL использует нестандартный порт во избежание конфликтов
3. **Все сервисы в Docker** - Включая Ingest (бывший Worker)
4. **Временные распарсенные файлы** - Сохраняются в `/home/alpaca/tmp_md` как .md для отладки/проверки
5. **Блокировка статусом** - Статус `processed` предотвращает состояние гонки при обработке очереди
6. **Русский язык** - Комментарии, логи, документация смешивают русский и английский; код/API на английском
7. **Изолированные микросервисы** - Все сервисы независимы, имеют собственные settings/repository

## Внешний доступ к API (Интернет)

### Архитектура доступа

Локальная машина находится за NAT без белого IP. Внешний доступ организован через **reverse SSH tunnel** на VDS:

```
Интернет → VDS (95.217.205.233:8443/HTTPS) → SSH туннель → Локальная машина → Docker-сервисы
```

- **VDS**: Hetzner, Ubuntu, IP: 95.217.205.233
- **Домен**: `api.alpaca-smart.com` (DNS A-запись на VDS)
- **SSL**: Let's Encrypt сертификат, HTTPS на порту 8443
- **SSH туннель**: autossh reverse tunnel через порт 2222

### Конфигурация nginx на VDS

Файл `/etc/nginx/sites-available/api.alpaca-smart.com`:
```nginx
server {
    listen 8443 ssl;
    server_name api.alpaca-smart.com;
    
    ssl_certificate /etc/letsencrypt/live/api.alpaca-smart.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.alpaca-smart.com/privkey.pem;
    
    # Chat Backend
    location /chat/ {
        proxy_pass http://localhost:8082/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    # Admin Backend  
    location /admin/ {
        proxy_pass http://localhost:8080/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    # Fallback
    location / {
        proxy_pass http://localhost:8080/;
    }
}
```

### SSH туннель (autossh)

Файл `/etc/systemd/system/autossh-tunnel.service` на локальной машине:
```ini
[Service]
ExecStart=/usr/bin/autossh -M 0 -N \
    -o "ServerAliveInterval 30" \
    -o "ServerAliveCountMax 3" \
    -R 2223:localhost:22 \
    -R 8080:localhost:8080 \
    -R 8082:localhost:8082 \
    vds
```

Управление:
```bash
sudo systemctl status autossh-tunnel   # Проверить статус
sudo systemctl restart autossh-tunnel  # Перезапустить
journalctl -u autossh-tunnel -f        # Логи
```

### Проброс портов через туннель

| Локальный порт | VDS порт | Сервис |
|---------------|----------|--------|
| 22 | 2223 | SSH (для доступа к локальной машине) |
| 8080 | 8080 | Admin Backend |
| 8082 | 8082 | Chat Backend |

### URL-адреса API

- **Admin Backend**: `https://api.alpaca-smart.com:8443/admin/`
  - Health: `/admin/health`
  - Docs: `/admin/docs`
- **Chat Backend**: `https://api.alpaca-smart.com:8443/chat/`
  - Health: `/chat/health`
  - Docs: `/chat/docs`

### ROOT_PATH для Swagger

При работе за reverse proxy с путевой маршрутизацией (path-based routing), FastAPI требует `root_path` для корректной генерации URL в Swagger UI:

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

### Известные проблемы с сетью

**Проблема**: Некоторые порты (не 8080) могут не работать через SSH туннель из определённых сетей. TCP-соединение устанавливается, но HTTP-ответы не возвращаются.

**Симптомы**:
- `curl` зависает после установки соединения
- Работает с мобильной сети, не работает из домашней
- На VDS `curl localhost:порт` работает

**Диагностика**:
```bash
# На VDS - проверить что туннель работает
curl -v http://localhost:8082/health

# На локальной машине - проверить Docker
curl http://localhost:8082/health

# Проверить туннель
ssh vds "netstat -tlnp | grep 808"
```

**Временное решение (если порт не работает напрямую)**:

1. Добавить локальный nginx как прокси:
```nginx
# /etc/nginx/sites-available/chat-backend
server {
    listen 8082;
    location / {
        proxy_pass http://127.0.0.1:18082;
    }
}
```

2. Изменить порт Docker на локальный:
```yaml
ports:
  - "127.0.0.1:18082:8000"  # Только localhost
```

3. nginx слушает 8082, проксирует на 18082 (Docker)

**Текущий статус**: Проблема обойдена использованием единого HTTPS-порта 8443 с path-based routing на VDS. Все сервисы доступны через этот порт.

## Изоляция микросервисов

**Все сервисы** — полностью изолированные Docker-контейнеры:

- Каждый имеет собственные `settings.py`, `repository.py`, `requirements.txt`
- Не зависят от `core/`, `utils/`, корневого `settings.py`
- Могут развёртываться и обновляться независимо

**При изменении схемы БД** обновите SQL во всех репозиториях:
- `services/file_watcher/src/repository.py`
- `services/ingest/src/repository.py`
- `services/chat_backend/src/repository.py`
- `services/admin_backend/src/database.py`

## Архитектурная дорожная карта

`docs/architecture_roadmap.md` фиксирует текущий план по снижению связанности:

1. **✅ Изоляция микросервисов** — FileWatcher и Admin Backend полностью изолированы от core/, имеют собственные репозитории.
2. **Bootstrap зависимостей** — вынести сборку сервисов из `main.py` в модуль bootstrap (пока в работе; worker всё ещё конфигурируется вручную).
3. **Чёткие границы domain/application** — домен экспонирует только контракты, а привязки реализаций происходят в bootstrap.
4. **Конфигурируемый embedder** — переключение между `custom_embedding` и `langchain_embedding` без правок кода.
5. **Совместимость и тесты** — удаление устаревших API после миграции тестов на новые use-case'ы.
6. **Документация** — README по слоям, актуальные инструкции по настройкам и bootstrap.

При планировании изменений держите эти шаги в голове: новые фичи должны приближать проект к этим целям и сопровождаться правками roadmap при необходимости.

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

# Запустить тесты
python tests/runner.py --suite all -v
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
