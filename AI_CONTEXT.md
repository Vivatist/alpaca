# Контекст для AI ассистента

> Этот файл содержит ключевую информацию для AI ассистента при работе в новом репозитории

---

## 📍 ВАЖНО: Старый репозиторий остаётся доступным!

**Расположение:** `/home/alpaca/alpaca-n8n`

**Что можно использовать без изменений:**
- ✅ **file-watcher** - `/home/alpaca/alpaca-n8n/file-watcher/` - ПОЛНОСТЬЮ рабочий, брать как есть
- ✅ **parsing** - `/home/alpaca/alpaca-n8n/parsing/` - ПОЛНОСТЬЮ рабочий, брать как есть
- ✅ **main-loop** - `/home/alpaca/alpaca-n8n/main-loop/` - ПОЛНОСТЬЮ рабочий, брать как есть
- ✅ **admin-backend** - `/home/alpaca/alpaca-n8n/admin-backend/` - контейнер готов, копировать целиком

**Эти компоненты протестированы и работают идеально. Не нужно переписывать с нуля - берите код оттуда!**

---

## 🎯 Цель проекта

Создание монолитной RAG (Retrieval-Augmented Generation) системы для управления корпоративными знаниями с автоматической обработкой документов.

---

## 📚 Наработанный опыт из старого проекта

### Что работало хорошо:

1. **File Watcher логика:**
   - Сканирование по SHA256 hash как источник истины
   - Статусная модель синхронизации через `status_sync`
   - Периодическое сканирование каждые 20 секунд
   - Фильтрация по расширениям, размеру, паттернам

2. **Парсинг документов:**
   - Unstructured API с `hi_res` стратегией
   - Эвристики для определения заголовков в markdown
   - Timeout 300 секунд для больших файлов
   - OCR для изображений (rus+eng)

3. **Admin Backend:**
   - REST API для мониторинга file_state и documents
   - Агрегированный dashboard endpoint
   - Healthchecks для всех сервисов
   - Интеграция с Docker API

4. **Интеграция с Ollama:**
   - qwen2.5:14b для LLM
   - bge-m3 для embeddings (1024 размерность)
   - Конфигурация для GPU: KEEP_ALIVE=-1, NUM_PARALLEL=2

### Проблемы старой архитектуры:

1. **N8N overhead:**
   - Сложно отлаживать workflow
   - Медленные итерации
   - Избыточная сложность
   - Нужен отдельный Redis

2. **Микросервисы:**
   - 5 отдельных сервисов
   - Дублирование кода (database.py в каждом)
   - Network overhead
   - Сложная синхронизация

3. **Разрозненная конфигурация:**
   - Переменные окружения в docker-compose
   - Нет централизованного settings.py
   - Сложно менять параметры

---

## 🏗️ Архитектурные решения

### Новая архитектура:

```
Монолитное FastAPI приложение (venv)
    ↓
├── API endpoints (FastAPI)
├── Background workers (APScheduler)
├── Core business logic
└── Database (asyncpg)
    
Внешние сервисы (Docker):
├── Unstructured API
├── Ollama (GPU)
├── Admin Backend (изолированный)
└── Supabase (PostgreSQL + pgvector)
```

### Почему такая архитектура:

1. **Монолит** - проще разрабатывать, отлаживать, деплоить
2. **Venv вместо контейнера** - быстрая разработка, hot reload
3. **Admin Backend отдельно** - изоляция мониторинга, Docker API
4. **Внешние сервисы в Docker** - изоляция сторонних компонентов

---

## 🗄️ Схема базы данных

### file_state (метаданные файлов)
```sql
CREATE TABLE file_state (
    id SERIAL PRIMARY KEY,
    file_path TEXT NOT NULL UNIQUE,
    file_size BIGINT NOT NULL,
    file_hash TEXT,                    -- SHA256
    file_mtime DOUBLE PRECISION,       -- Unix timestamp
    status_sync TEXT DEFAULT 'ok',     -- ok|added|updated|processed|deleted|error
    last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Статусы status_sync:**
- `ok` - файл обработан успешно, синхронизирован
- `added` - новый файл, требует обработки
- `updated` - файл изменён, требует переобработки
- `processed` - файл в процессе обработки (занимает слот)
- `deleted` - файл удалён с диска
- `error` - ошибка при обработке

### documents (векторные чанки)
```sql
CREATE TABLE documents (
    id BIGSERIAL PRIMARY KEY,
    file_hash TEXT NOT NULL,
    file_path TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding VECTOR(1024),           -- bge-m3 embeddings
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT unique_chunk UNIQUE (file_hash, chunk_index)
);
```

---

## 🔄 Workflow обработки документов

### Старый workflow (N8N):
```
Webhook → Parse (Unstructured) → Chunk → Embed (Ollama) → Save to DB
```

### Новый workflow (Python):
```python
async def process_document(file_path, file_hash):
    # 1. Parse
    text = await parser.parse(file_path)
    
    # 2. Chunk
    chunks = chunker.chunk_text(text, size=1000, overlap=200)
    
    # 3. Embed
    embeddings = await embedder.generate(chunks)
    
    # 4. Save
    await db.save_documents(file_hash, chunks, embeddings)
    
    # 5. Update status
    await db.update_status(file_hash, 'ok')
```

---

## 🔧 Конфигурация (settings.py)

### Ключевые параметры:

```python
# File Monitoring
MONITORED_PATH = "/monitored_folder"
ALLOWED_EXTENSIONS = [".docx", ".pdf", ".txt", ".xlsx", ".pptx"]
SCAN_INTERVAL = 20  # секунды
FILE_MIN_SIZE = 500  # байты
FILE_MAX_SIZE = 5_000_000  # 5MB

# RAG
CHUNK_SIZE = 1000  # символов
CHUNK_OVERLAP = 200
TOP_K_RESULTS = 5
SIMILARITY_THRESHOLD = 0.7

# Processing
MAX_CONCURRENT_PROCESSING = 2  # максимум одновременных обработок
```

---

## 📦 Зависимости (requirements.txt)

### Основные:
```
fastapi==0.115.0
uvicorn[standard]==0.31.0
asyncpg==0.30.0
pydantic==2.9.0
pydantic-settings==2.5.0
httpx==0.27.0
apscheduler==3.10.4
python-multipart==0.0.9
```

### Для обработки:
```
langchain==0.3.0
langchain-text-splitters==0.3.0
```

### Для разработки:
```
pytest==8.3.0
pytest-asyncio==0.24.0
black==24.0.0
ruff==0.6.0
```

### Для миграций:
```
alembic==1.13.0
```

---

## 🧪 Примеры кода

### 1. File Watcher

**ВАЖНО: Рабочий код в `/home/alpaca/alpaca-n8n/file-watcher/`**

Ключевые файлы:
- `app/main.py` - основной цикл сканирования
- `app/scanner.py` - логика сканирования файлов
- `app/database.py` - синхронизация с БД
- `app/file_filter.py` - фильтрация файлов
- `app/vector_sync.py` - синхронизация status_sync

**Использовать как есть!** Этот код полностью протестирован и работает.

Пример из `scanner.py`:
```python
import hashlib
from pathlib import Path

def calculate_hash(file_path: str) -> str:
    """SHA256 hash файла"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def scan_directory(monitored_path: Path, allowed_extensions: list) -> list:
    """Рекурсивное сканирование с фильтрацией"""
    files = []
    for file_path in monitored_path.rglob('*'):
        if file_path.is_file() and file_path.suffix in allowed_extensions:
            files.append({
                'file_path': str(file_path.relative_to(monitored_path)),
                'file_size': file_path.stat().st_size,
                'file_hash': calculate_hash(str(file_path)),
                'file_mtime': file_path.stat().st_mtime
            })
    return files
```

### 2. Parser

**ВАЖНО: Рабочий код в `/home/alpaca/alpaca-n8n/parsing/`**

Ключевые файлы:
- `app/main.py` - FastAPI сервис парсинга
- `Dockerfile` - готовый контейнер
- `requirements.txt` - зависимости

**Использовать как есть!** FastAPI endpoints полностью рабочие:
- `POST /parse` - парсинг файла из monitored_folder
- `POST /parse/upload` - парсинг загруженного файла
- `GET /health` - healthcheck

Пример из `main.py`:
```python
async def parse_document(file_path: str) -> str:
    """Парсинг через Unstructured API"""
    with open(file_path, 'rb') as f:
        file_content = f.read()
    
    files = {'files': (Path(file_path).name, file_content)}
    data = {
        'strategy': 'hi_res',
        'ocr_languages': 'rus+eng',
        'pdf_infer_table_structure': 'true',
    }
    
    async with httpx.AsyncClient(timeout=300) as client:
        response = await client.post(
            f"{UNSTRUCTURED_URL}/general/v0/general",
            files=files,
            data=data
        )
        result = response.json()
        
        # Склеиваем элементы с эвристиками для markdown
        content_parts = []
        for element in result:
            text = element.get('text', '')
            element_type = element.get('type', 'NarrativeText')
            
            if element_type == 'Title':
                content_parts.append(f"\n## {text}\n")
            elif element_type == 'Header':
                content_parts.append(f"\n### {text}\n")
            else:
                content_parts.append(text)
        
        return '\n'.join(content_parts)
```

### 3. Embedder (новая логика):

```python
async def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Генерация эмбеддингов через Ollama bge-m3"""
    embeddings = []
    
    async with httpx.AsyncClient(timeout=120) as client:
        for text in texts:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/embeddings",
                json={
                    "model": "bge-m3",
                    "prompt": text
                }
            )
            result = response.json()
            embeddings.append(result['embedding'])
    
    return embeddings
```

### 4. Main Loop

**ВАЖНО: Рабочий код в `/home/alpaca/alpaca-n8n/main-loop/`**

Ключевые файлы:
- `app/main.py` - основной цикл обработки
- `app/database.py` - работа с БД

**Использовать как есть!** Логика обработки очереди полностью работает.

### 5. Admin Backend

**ВАЖНО: Рабочий контейнер в `/home/alpaca/alpaca-n8n/admin-backend/`**

Ключевые файлы:
- `app/main.py` - FastAPI с полным REST API
- `app/database.py` - интеграция с БД
- `Dockerfile` - готовый контейнер
- `requirements.txt` - зависимости

**Копировать целиком в новый проект!** Все endpoints работают:
- `/api/dashboard` - агрегированный dashboard
- `/api/file-state/*` - статистика и управление файлами
- `/api/documents/*` - работа с документами
- `/api/n8n/*` - интеграция с N8N (можно убрать)
- `/health` - healthcheck

### 6. Database Sync

Полная логика в `/home/alpaca/alpaca-n8n/file-watcher/app/database.py`:

```python
def sync_by_hash(disk_files: list) -> dict:
    """Синхронизация file_state с диском по hash"""
    stats = {'added': 0, 'updated': 0, 'unchanged': 0, 'deleted': 0}
    
    # Получаем текущее состояние из БД
    db_files = fetch_all("SELECT file_hash, file_path, file_size FROM file_state")
    db_by_hash = {f['file_hash']: f for f in db_files}
    disk_by_hash = {f['file_hash']: f for f in disk_files}
    
    # Обрабатываем файлы с диска
    for file_hash, disk_file in disk_by_hash.items():
        if file_hash not in db_by_hash:
            # Новый файл
            execute("""
                INSERT INTO file_state (file_path, file_size, file_hash, file_mtime, status_sync)
                VALUES (?, ?, ?, ?, 'added')
            """, disk_file['file_path'], disk_file['file_size'], file_hash, disk_file['file_mtime'])
            stats['added'] += 1
        else:
            db_file = db_by_hash[file_hash]
            if disk_file['file_path'] != db_file['file_path']:
                # Файл перемещён
                execute("UPDATE file_state SET file_path = ? WHERE file_hash = ?", 
                       disk_file['file_path'], file_hash)
                stats['updated'] += 1
            else:
                stats['unchanged'] += 1
    
    # Помечаем удалённые файлы
    for file_hash in db_by_hash:
        if file_hash not in disk_by_hash:
            execute("UPDATE file_state SET status_sync = 'deleted' WHERE file_hash = ?", file_hash)
            stats['deleted'] += 1
    
    return stats
```

---

## 🔧 Стратегия портирования кода

### Что копировать из старого репозитория `/home/alpaca/alpaca-n8n`:

1. **file-watcher/** → `app/core/file_watcher.py` и `app/workers/scheduler.py`
   ```bash
   # Взять из старого проекта:
   # - app/main.py (основной цикл)
   # - app/scanner.py (сканирование)
   # - app/database.py (sync_by_hash логика)
   # - app/file_filter.py (фильтрация)
   # - app/vector_sync.py (status_sync)
   ```

2. **parsing/** → `app/core/parser.py`
   ```bash
   # Взять из старого проекта:
   # - app/main.py (убрать FastAPI, оставить логику)
   ```

3. **main-loop/** → `app/workers/file_processor.py`
   ```bash
   # Взять из старого проекта:
   # - app/main.py (логика очереди и обработки)
   # - app/database.py (методы работы с pending files)
   ```

4. **admin-backend/** → `docker/admin-backend/`
   ```bash
   # Скопировать целиком:
   cp -r /home/alpaca/alpaca-n8n/admin-backend docker/
   # Только убрать N8N endpoints из app/main.py
   ```

### НЕ переписывать с нуля! Адаптировать существующий код!

---

## 🚀 Запуск и разработка

### Разработка:
```bash
# 1. Создать venv
python3.12 -m venv venv
source venv/bin/activate

# 2. Установить зависимости
pip install -r requirements.txt

# 3. Настроить .env
cp .env.example .env
# Отредактировать DATABASE_URL и другие параметры

# 4. Запустить внешние сервисы
cd docker && docker-compose up -d

# 5. Применить миграции
alembic upgrade head

# 6. Запустить приложение
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Production:
```bash
# Systemd service
sudo systemctl start alpaca-rag
sudo systemctl enable alpaca-rag

# Логи
journalctl -u alpaca-rag -f
```

---

## 🔍 Troubleshooting

### Частые проблемы:

1. **Ollama не отвечает:**
   - Проверить: `curl http://localhost:11434/api/tags`
   - Загрузить модели: `ollama pull bge-m3 && ollama pull qwen2.5:14b`

2. **Unstructured timeout:**
   - Увеличить UNSTRUCTURED_TIMEOUT
   - Проверить размер файла (макс 5MB)

3. **pgvector ошибки:**
   - Включить расширение: `CREATE EXTENSION IF NOT EXISTS vector;`
   - Проверить размерность: bge-m3 = 1024

4. **File watcher не видит изменения:**
   - Проверить MONITORED_PATH
   - Проверить расширения в ALLOWED_EXTENSIONS
   - Проверить размер файла (FILE_MIN_SIZE, FILE_MAX_SIZE)

---

## 📊 Мониторинг

### Ключевые метрики:

1. **file_state статистика:**
   ```sql
   SELECT status_sync, COUNT(*) 
   FROM file_state 
   GROUP BY status_sync;
   ```

2. **documents статистика:**
   ```sql
   SELECT 
       COUNT(*) as total_chunks,
       COUNT(DISTINCT file_hash) as unique_files,
       AVG(array_length(embedding::float[], 1)) as avg_embedding_dim
   FROM documents;
   ```

3. **Очередь обработки:**
   ```sql
   SELECT file_path, file_size, status_sync, last_checked
   FROM file_state
   WHERE status_sync IN ('added', 'updated')
   ORDER BY last_checked ASC;
   ```

---

## 📝 Чеклист для AI ассистента

При работе в новом репозитории проверь:

- [ ] Прочитан MIGRATION_PLAN.md
- [ ] Прочитан этот AI_CONTEXT.md
- [ ] **ВАЖНО:** Знаю что старый репозиторий в `/home/alpaca/alpaca-n8n`
- [ ] **ВАЖНО:** Понимаю что file-watcher, parsing, main-loop, admin-backend - брать как есть!
- [ ] Изучена структура settings.py
- [ ] Понятна логика status_sync
- [ ] Понятен workflow обработки документов
- [ ] Знакомы с примерами кода выше
- [ ] Понятна схема БД (file_state + documents)
- [ ] Известны ключевые параметры конфигурации

---

## 🎓 Глоссарий

- **file_state** - таблица с метаданными файлов (путь, hash, размер, статус)
- **documents** - таблица с векторными чанками (текст + embedding)
- **status_sync** - статус синхронизации файла (ok|added|updated|processed|deleted|error)
- **file_hash** - SHA256 хэш файла, источник истины для определения изменений
- **chunk** - фрагмент текста (обычно 1000 символов с overlap 200)
- **embedding** - векторное представление текста (bge-m3, размерность 1024)
- **RAG** - Retrieval-Augmented Generation, поиск + генерация ответа LLM
- **Unstructured API** - сервис для парсинга документов (PDF, DOCX, etc)
- **Ollama** - локальный LLM сервер (qwen2.5 для генерации, bge-m3 для embeddings)

---

**Удачи в разработке! 🚀**
