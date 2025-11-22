# План миграции на монолитную архитектуру

> **Дата создания:** 22 ноября 2025  
> **Статус:** Планирование  
> **Версия:** 2.0.0

---

## 📊 АНАЛИЗ ТЕКУЩЕЙ АРХИТЕКТУРЫ

### Текущие микросервисы:
1. **file-watcher** - сканирование файлов, обновление file_state
2. **main-loop** - управление очередью обработки, вызов N8N webhooks
3. **parsing** - FastAPI wrapper для Unstructured API
4. **admin-backend** - REST API для мониторинга
5. **n8n + workers** - оркестрация workflow с RAG/LLM

### Текущая БД (Supabase):
- `file_state` - метаданные файлов (путь, hash, размер, статус)
- `documents` - векторные чанки документов (pgvector)
- N8N системные таблицы

### Что работает хорошо:
- ✅ Логика file-watcher (сканирование по hash)
- ✅ Синхронизация file_state через status_sync
- ✅ Парсинг через Unstructured API (hi_res стратегия)
- ✅ Admin backend для мониторинга
- ✅ Интеграция с Ollama (qwen2.5 + bge-m3)

### Проблемы текущей архитектуры:
- ❌ N8N - избыточная сложность для простых задач
- ❌ Много микросервисов - сложность разработки и отладки
- ❌ Сетевые вызовы между сервисами
- ❌ Дублирование логики (database.py в каждом сервисе)
- ❌ Разрозненная конфигурация

---

## 🎯 НОВАЯ АРХИТЕКТУРА (Монолит)

### Принципы:
1. **Единый процесс** - FastAPI приложение + фоновые задачи
2. **Отказ от N8N** - вся логика в Python коде
3. **Отказ от микросервисов** - монолитное приложение
4. **Контейнеры только для внешних сервисов** (Unstructured, Ollama, Supabase)
5. **Admin-backend остаётся отдельно** - для изоляции мониторинга
6. **Виртуальное окружение** вместо контейнеров для основного приложения
7. **Python 3.12**
8. **Централизованная конфигурация** в settings.py

### Структура репозитория:
```
alpaca-rag/
├── .env                          # Конфигурация окружения
├── .gitignore
├── README.md                     # Документация проекта
├── ARCHITECTURE.md               # Описание архитектуры
├── requirements.txt              # Все зависимости
├── settings.py                   # Централизованная конфигурация
├── main.py                       # Точка входа FastAPI приложения
├── pyproject.toml                # Python 3.12, poetry/pip
│
├── app/
│   ├── __init__.py
│   │
│   ├── api/                      # FastAPI endpoints
│   │   ├── __init__.py
│   │   ├── documents.py          # CRUD документов
│   │   ├── search.py             # Векторный поиск
│   │   ├── admin.py              # Мониторинг (из старого admin-backend)
│   │   └── health.py             # Healthchecks
│   │
│   ├── core/                     # Бизнес-логика
│   │   ├── __init__.py
│   │   ├── file_watcher.py       # Сканирование файлов (из старого file-watcher)
│   │   ├── parser.py             # Парсинг через Unstructured (из старого parsing)
│   │   ├── chunker.py            # Чанкирование текста
│   │   ├── embedder.py           # Генерация эмбеддингов (Ollama bge-m3)
│   │   └── rag.py                # RAG логика (Ollama qwen2.5)
│   │
│   ├── db/                       # Database
│   │   ├── __init__.py
│   │   ├── connection.py         # PostgreSQL connection pool
│   │   ├── models.py             # SQLAlchemy/Pydantic models
│   │   └── migrations/           # Alembic миграции
│   │       └── versions/
│   │
│   ├── workers/                  # Background tasks
│   │   ├── __init__.py
│   │   ├── file_processor.py     # Обработка файлов (замена N8N)
│   │   └── scheduler.py          # Фоновые задачи (APScheduler)
│   │
│   └── utils/
│       ├── __init__.py
│       ├── logging.py
│       └── validators.py
│
├── docker/
│   ├── docker-compose.yml        # Только внешние сервисы
│   ├── admin-backend/            # Отдельный контейнер для admin
│   │   ├── Dockerfile
│   │   └── app/
│   └── .env.example
│
├── tests/
│   ├── __init__.py
│   ├── test_parser.py
│   ├── test_embedder.py
│   ├── test_chunker.py
│   └── test_rag.py
│
└── scripts/
    ├── migrate_db.py             # Миграция данных из старой БД
    ├── setup_dev.sh              # Настройка dev окружения
    └── init_models.sh            # Загрузка моделей в Ollama
```

---

## 🔧 settings.py (Централизованная конфигурация)

```python
"""Централизованная конфигурация ALPACA RAG системы"""

from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Optional

class Settings(BaseSettings):
    """Настройки приложения через переменные окружения"""
    
    # Application
    APP_NAME: str = "ALPACA RAG"
    VERSION: str = "2.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "production"  # development | production
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4
    RELOAD: bool = False  # Hot reload для разработки
    
    # Database (Supabase PostgreSQL)
    DATABASE_URL: str
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_ECHO: bool = False  # SQL logging
    
    # File Monitoring
    MONITORED_PATH: Path = Path("/monitored_folder")
    ALLOWED_EXTENSIONS: list[str] = [".docx", ".pdf", ".txt", ".xlsx", ".pptx"]
    SCAN_INTERVAL: int = 20  # Секунды между сканированиями
    FILE_MIN_SIZE: int = 500  # Байты
    FILE_MAX_SIZE: int = 5_000_000  # 5MB
    EXCLUDED_DIRS: list[str] = ["TMP", "temp", "cache", "__pycache__"]
    EXCLUDED_PATTERNS: list[str] = ["~*", ".*", "*.tmp", "*.swp"]
    
    # Unstructured API (парсинг документов)
    UNSTRUCTURED_URL: str = "http://localhost:9000"
    UNSTRUCTURED_TIMEOUT: int = 300  # 5 минут
    UNSTRUCTURED_STRATEGY: str = "hi_res"  # hi_res | fast | auto
    
    # Ollama (LLM + Embeddings)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_EMBED_MODEL: str = "bge-m3"
    OLLAMA_LLM_MODEL: str = "qwen2.5:14b"
    OLLAMA_TIMEOUT: int = 120  # 2 минуты
    
    # RAG Settings
    CHUNK_SIZE: int = 1000  # Символов в чанке
    CHUNK_OVERLAP: int = 200  # Перекрытие между чанками
    TOP_K_RESULTS: int = 5  # Топ результатов для RAG
    SIMILARITY_THRESHOLD: float = 0.7  # Порог схожести
    
    # Background Tasks
    MAX_CONCURRENT_PROCESSING: int = 2  # Макс одновременных обработок
    TASK_QUEUE_MAX_SIZE: int = 100
    PROCESSING_BATCH_SIZE: int = 10
    
    # Admin Backend
    ADMIN_API_KEY: Optional[str] = None
    CORS_ORIGINS: list[str] = ["*"]
    
    # Logging
    LOG_LEVEL: str = "INFO"  # DEBUG | INFO | WARNING | ERROR
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

settings = Settings()
```

---

## 📦 docker-compose.yml (Только внешние сервисы)

```yaml
name: alpaca-rag

services:
  # Unstructured API для парсинга документов
  unstructured:
    image: downloads.unstructured.io/unstructured-io/unstructured-api:latest
    restart: always
    ports:
      - "9000:8000"
    environment:
      - UNSTRUCTURED_ALLOWED_MIMETYPES=application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.openxmlformats-officedocument.presentationml.presentation,text/plain
      - UNSTRUCTURED_MEMORY_FREE_MINIMUM_MB=512
      - TZ=Europe/Moscow
      - LANG=C.UTF-8
      - LC_ALL=C.UTF-8
      - PYTHONIOENCODING=utf-8
      - UNSTRUCTURED_LANGUAGE=rus,eng
      - UNSTRUCTURED_OCR_LANGUAGES=rus+eng
      - UNSTRUCTURED_USE_OCR_ALWAYS=auto
      - UNSTRUCTURED_PARALLEL_MODE=true
      - UNSTRUCTURED_PARALLEL_NUM_WORKERS=2
    volumes:
      - unstructured_data:/app/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/healthcheck"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    networks:
      - alpaca_network

  # Ollama для LLM и эмбеддингов
  ollama:
    image: ollama/ollama:latest
    restart: always
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - NVIDIA_DRIVER_CAPABILITIES=compute,utility
      - OLLAMA_NUM_GPU=1
      - OLLAMA_GPU_LAYERS=999
      - OLLAMA_MAX_LOADED_MODELS=2  # qwen2.5 + bge-m3
      - OLLAMA_KEEP_ALIVE=-1  # Держать в памяти постоянно
      - OLLAMA_NUM_PARALLEL=2
      - OLLAMA_MAX_QUEUE=10
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [compute,utility]
    healthcheck:
      test: ["CMD", "ollama", "list"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - alpaca_network

  # Admin Backend (остается в контейнере для изоляции)
  admin-backend:
    build: ./admin-backend
    restart: unless-stopped
    ports:
      - "8080:8080"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - TZ=Europe/Moscow
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    depends_on:
      - unstructured
      - ollama
    networks:
      - alpaca_network

volumes:
  unstructured_data:
  ollama_data:

networks:
  alpaca_network:
    name: alpaca_network
    driver: bridge
```

---

## 🗄️ СХЕМА БД (Миграция)

### Таблицы для миграции из старой БД:

#### 1. file_state (переносится без изменений)
```sql
CREATE TABLE file_state (
    id SERIAL PRIMARY KEY,
    file_path TEXT NOT NULL UNIQUE,
    file_size BIGINT NOT NULL,
    file_hash TEXT,
    file_mtime DOUBLE PRECISION,
    status_sync TEXT DEFAULT 'ok',  -- ok | added | updated | processed | deleted | error
    last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_file_hash ON file_state(file_hash);
CREATE INDEX idx_status_sync ON file_state(status_sync);
CREATE INDEX idx_file_path ON file_state(file_path);
```

#### 2. documents (векторные чанки - переносится без изменений)
```sql
-- Включаем pgvector если ещё не включено
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE documents (
    id BIGSERIAL PRIMARY KEY,
    file_hash TEXT NOT NULL,
    file_path TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding VECTOR(1024),  -- bge-m3 размерность
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT unique_chunk UNIQUE (file_hash, chunk_index)
);

CREATE INDEX idx_documents_file_hash ON documents(file_hash);
CREATE INDEX idx_documents_file_path ON documents(file_path);
CREATE INDEX idx_documents_embedding ON documents USING ivfflat (embedding vector_cosine_ops);
```

### Скрипт миграции данных:
```sql
-- 1. Создаём структуру таблиц в новой БД (выше)

-- 2. Копируем file_state
INSERT INTO new_db.file_state 
SELECT * FROM old_db.file_state;

-- 3. Копируем documents (векторные чанки)
INSERT INTO new_db.documents 
SELECT * FROM old_db.documents;

-- 4. Проверяем количество записей
SELECT 
    (SELECT COUNT(*) FROM new_db.file_state) as file_state_count,
    (SELECT COUNT(*) FROM new_db.documents) as documents_count;
```

---

## 🔄 НОВАЯ АРХИТЕКТУРА ОБРАБОТКИ

### Замена N8N Workflow на Python код:

```python
# app/workers/file_processor.py

"""Обработка документов - замена N8N workflow"""

import asyncio
from pathlib import Path
from app.core.parser import parse_document
from app.core.chunker import chunk_text
from app.core.embedder import generate_embeddings
from app.db.connection import get_db
from settings import settings
import logging

logger = logging.getLogger(__name__)


async def process_document(file_path: str, file_hash: str) -> bool:
    """
    Полный цикл обработки документа (замена N8N workflow)
    
    Шаги:
    1. Парсинг через Unstructured API
    2. Чанкирование текста
    3. Генерация эмбеддингов через Ollama (bge-m3)
    4. Сохранение чанков в documents
    5. Обновление статуса в file_state
    
    Args:
        file_path: Относительный путь к файлу
        file_hash: SHA256 хэш файла
    
    Returns:
        bool: True если успешно, False если ошибка
    """
    logger.info(f"Processing: {file_path} (hash: {file_hash[:8]}...)")
    
    try:
        # 1. Парсинг документа
        full_path = settings.MONITORED_PATH / file_path
        parsed_text = await parse_document(str(full_path))
        
        if not parsed_text or len(parsed_text) < 100:
            raise ValueError("Parsed text too short or empty")
        
        logger.info(f"Parsed {len(parsed_text)} chars")
        
        # 2. Чанкирование
        chunks = chunk_text(
            parsed_text,
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP
        )
        
        logger.info(f"Created {len(chunks)} chunks")
        
        # 3. Генерация эмбеддингов
        embeddings = await generate_embeddings(chunks)
        
        logger.info(f"Generated {len(embeddings)} embeddings")
        
        # 4. Сохранение в БД
        async with get_db() as db:
            # Удаляем старые чанки если есть
            await db.execute(
                "DELETE FROM documents WHERE file_hash = $1",
                file_hash
            )
            
            # Вставляем новые чанки
            for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                await db.execute("""
                    INSERT INTO documents 
                    (file_hash, file_path, chunk_index, chunk_text, embedding)
                    VALUES ($1, $2, $3, $4, $5)
                """, file_hash, file_path, idx, chunk, embedding)
            
            # 5. Обновляем статус на 'ok'
            await db.execute("""
                UPDATE file_state 
                SET status_sync = 'ok', last_checked = NOW()
                WHERE file_hash = $1
            """, file_hash)
        
        logger.info(f"✓ Successfully processed {file_path}")
        return True
        
    except Exception as e:
        logger.error(f"✗ Failed to process {file_path}: {e}", exc_info=True)
        
        # Помечаем как error
        try:
            async with get_db() as db:
                await db.execute("""
                    UPDATE file_state 
                    SET status_sync = 'error', last_checked = NOW()
                    WHERE file_hash = $1
                """, file_hash)
        except Exception as db_error:
            logger.error(f"Failed to update error status: {db_error}")
        
        return False


async def process_queue():
    """
    Обработка очереди файлов (замена main-loop)
    
    Логика:
    - Берём файлы со статусом 'added' или 'updated'
    - Обрабатываем не больше MAX_CONCURRENT_PROCESSING одновременно
    - Пропускаем если уже есть 'processed' файлы
    """
    async with get_db() as db:
        # Проверяем текущее количество обрабатываемых
        result = await db.fetchval("""
            SELECT COUNT(*) FROM file_state 
            WHERE status_sync = 'processed'
        """)
        
        current_processing = result or 0
        slots_available = settings.MAX_CONCURRENT_PROCESSING - current_processing
        
        if slots_available <= 0:
            logger.debug("No available slots for processing")
            return
        
        # Получаем файлы для обработки
        files = await db.fetch("""
            SELECT file_path, file_hash, file_size
            FROM file_state
            WHERE status_sync IN ('added', 'updated')
            ORDER BY last_checked ASC
            LIMIT $1
        """, slots_available)
        
        if not files:
            return
        
        logger.info(f"Processing {len(files)} files")
        
        # Помечаем как 'processed'
        for file in files:
            await db.execute("""
                UPDATE file_state 
                SET status_sync = 'processed'
                WHERE file_hash = $1
            """, file['file_hash'])
        
        # Обрабатываем параллельно
        tasks = [
            process_document(file['file_path'], file['file_hash'])
            for file in files
        ]
        
        await asyncio.gather(*tasks)
```

---

## 📋 ПЛАН МИГРАЦИИ (пошагово)

### Этап 1: Подготовка (1-2 дня)
- [ ] 1.1 Создать новый репозиторий `alpaca-rag` на GitHub
- [ ] 1.2 Скопировать этот MIGRATION_PLAN.md в новый репозиторий
- [ ] 1.3 Настроить Python 3.12 + venv
- [ ] 1.4 Создать структуру директорий
- [ ] 1.5 Создать `settings.py`
- [ ] 1.6 Настроить `.env` файл
- [ ] 1.7 Создать `requirements.txt`

### Этап 2: Перенос core логики (3-4 дня)
- [ ] 2.1 Портировать `file-watcher` → `app/core/file_watcher.py`
  - Взять логику из `/home/alpaca/alpaca-n8n/file-watcher/app/scanner.py`
  - Взять логику из `/home/alpaca/alpaca-n8n/file-watcher/app/database.py`
  - Адаптировать под новую структуру
  
- [ ] 2.2 Портировать `parsing` → `app/core/parser.py`
  - Взять из `/home/alpaca/alpaca-n8n/parsing/app/main.py`
  - Убрать FastAPI обёртку, оставить только логику парсинга
  
- [ ] 2.3 Реализовать `app/core/chunker.py`
  - Разделение текста на чанки с перекрытием
  - Сохранение метаданных (позиция в документе)
  
- [ ] 2.4 Реализовать `app/core/embedder.py`
  - Интеграция с Ollama API
  - Модель bge-m3 для эмбеддингов
  - Батчинг запросов
  
- [ ] 2.5 Реализовать `app/core/rag.py`
  - Векторный поиск по documents
  - Формирование контекста для LLM
  - Интеграция с Ollama qwen2.5

### Этап 3: База данных (1-2 дня)
- [ ] 3.1 Создать чистую Supabase БД (новый проект)
- [ ] 3.2 Настроить `app/db/connection.py` (asyncpg pool)
- [ ] 3.3 Создать `app/db/models.py` (Pydantic models)
- [ ] 3.4 Настроить Alembic для миграций
- [ ] 3.5 Создать скрипт `scripts/migrate_db.py`
- [ ] 3.6 Выполнить миграцию данных:
  - Экспорт file_state из старой БД
  - Экспорт documents из старой БД
  - Импорт в новую БД
  - Проверка целостности

### Этап 4: Workers и фоновые задачи (2-3 дня)
- [ ] 4.1 Реализовать `app/workers/file_processor.py`
  - process_document() - замена N8N workflow
  - process_queue() - замена main-loop
  
- [ ] 4.2 Реализовать `app/workers/scheduler.py`
  - APScheduler для периодических задач
  - Запуск file_watcher каждые SCAN_INTERVAL секунд
  - Запуск process_queue
  
- [ ] 4.3 Интеграция всех компонентов в main.py

### Этап 5: API endpoints (2 дня)
- [ ] 5.1 `app/api/health.py` - healthchecks
- [ ] 5.2 `app/api/documents.py` - CRUD документов
- [ ] 5.3 `app/api/search.py` - векторный поиск
- [ ] 5.4 `app/api/admin.py` - мониторинг (из старого admin-backend)
- [ ] 5.5 Настроить CORS и middleware

### Этап 6: Admin Backend (1 день)
- [ ] 6.1 Скопировать admin-backend в docker/admin-backend/
- [ ] 6.2 Обновить admin-backend для работы с новой БД
- [ ] 6.3 Обновить эндпоинты (убрать N8N интеграцию)

### Этап 7: Тесты (2 дня)
- [ ] 7.1 Unit тесты для parser
- [ ] 7.2 Unit тесты для chunker
- [ ] 7.3 Unit тесты для embedder
- [ ] 7.4 Integration тесты для file_processor
- [ ] 7.5 Настроить pytest

### Этап 8: Документация (1 день)
- [ ] 8.1 README.md с инструкциями по установке
- [ ] 8.2 ARCHITECTURE.md с описанием архитектуры
- [ ] 8.3 API документация (OpenAPI/Swagger)
- [ ] 8.4 Комментарии в коде

### Этап 9: Деплой (1-2 дня)
- [ ] 9.1 Настроить docker-compose.yml
- [ ] 9.2 Создать systemd service для основного приложения
- [ ] 9.3 Настроить nginx reverse proxy
- [ ] 9.4 Тестирование на production сервере
- [ ] 9.5 Мониторинг и логирование

### Этап 10: Финализация (1 день)
- [ ] 10.1 Выключить старые микросервисы
- [ ] 10.2 Удалить N8N и связанные сервисы
- [ ] 10.3 Проверить работу всей системы
- [ ] 10.4 Backup старой БД
- [ ] 10.5 Документировать изменения

**Общее время:** ~15-20 дней

---

## ⚡ ПРЕИМУЩЕСТВА НОВОЙ АРХИТЕКТУРЫ

### Для разработки:
- ✅ **Простота отладки** - весь код в одном процессе
- ✅ **Единая кодовая база** - нет дублирования
- ✅ **Быстрые итерации** - не нужно пересобирать контейнеры
- ✅ **Меньше зависимостей** - убрали N8N, Redis, лишние контейнеры

### Для производительности:
- ✅ **Нет network overhead** - все в памяти
- ✅ **Shared connection pool** - одно подключение к БД
- ✅ **Меньше контекстных переключений**
- ✅ **Эффективное использование ресурсов**

### Для надежности:
- ✅ **Меньше точек отказа** - 1 процесс вместо 5
- ✅ **Проще monitoring** - один процесс, одни логи
- ✅ **Понятные ошибки** - весь stack trace виден
- ✅ **Atomic operations** - транзакции работают правильно

### Для эксплуатации:
- ✅ **Простой деплой** - один systemd service
- ✅ **Единая конфигурация** - один .env файл
- ✅ **Меньше ресурсов** - не нужны Docker overhead
- ✅ **Проще масштабирование** - через uvicorn workers

---

## 📝 ВАЖНЫЕ ЗАМЕТКИ

### Что нужно помнить при миграции:

1. **file_state.status_sync** - ключевое поле для синхронизации
   - `ok` - файл обработан успешно
   - `added` - новый файл, требует обработки
   - `updated` - файл изменился, требует переобработки
   - `processed` - файл в процессе обработки
   - `deleted` - файл удалён с диска
   - `error` - ошибка при обработке

2. **file_hash как источник истины** - сравниваем hash для определения изменений

3. **Унаследованная логика file-watcher**:
   ```python
   # Из старого file-watcher/app/scanner.py
   def calculate_hash(file_path):
       # SHA256 хэш файла
   
   def scan():
       # Рекурсивное сканирование с фильтрацией
   
   # Из старого file-watcher/app/database.py
   def sync_by_hash(files):
       # Синхронизация file_state с диском
   ```

4. **Унаследованная логика parsing**:
   ```python
   # Из старого parsing/app/main.py
   async def parse_document(file_path):
       # Unstructured API с hi_res стратегией
       # Эвристики для markdown форматирования
   ```

5. **Новая логика chunker**:
   - Использовать langchain.text_splitter.RecursiveCharacterTextSplitter
   - Chunk size: 1000 символов
   - Overlap: 200 символов

6. **Интеграция с Ollama**:
   ```python
   # Embeddings через bge-m3
   POST http://localhost:11434/api/embeddings
   {
     "model": "bge-m3",
     "prompt": "text to embed"
   }
   
   # LLM через qwen2.5
   POST http://localhost:11434/api/generate
   {
     "model": "qwen2.5:14b",
     "prompt": "question with context"
   }
   ```

---

## 🔗 КОНТЕКСТ ДЛЯ AI АССИСТЕНТА

### Файлы для изучения при старте в новом репозитории:

1. **MIGRATION_PLAN.md** (этот файл) - полный план миграции
2. **ARCHITECTURE.md** - создать с описанием архитектуры
3. **settings.py** - пример конфигурации выше
4. **.env.example** - создать с примерами переменных

### Ключевые решения и их обоснование:

**Почему отказались от N8N:**
- Избыточная сложность для простых задач
- Сложно отлаживать workflow
- Медленные итерации (нужно править через UI)
- Проще всё на Python

**Почему отказались от микросервисов:**
- Небольшой проект, не требует масштабирования
- Network overhead между сервисами
- Дублирование кода (database.py в каждом)
- Сложность разработки и отладки

**Почему оставили admin-backend в контейнере:**
- Изоляция мониторинга от основного приложения
- Доступ к Docker API требует root
- Отдельный порт и lifecycle

**Почему виртуальное окружение вместо контейнера:**
- Быстрее разработка (hot reload)
- Проще отладка (attach debugger)
- Меньше overhead
- Контейнеры только для сторонних сервисов

### Технологический стек:

- **Python 3.12** - современный Python
- **FastAPI** - async REST API
- **asyncpg** - async PostgreSQL драйвер
- **Pydantic** - валидация и настройки
- **APScheduler** - фоновые задачи
- **httpx** - async HTTP клиент
- **langchain** - text splitting
- **pytest** - тестирование
- **Alembic** - миграции БД

---

## 📞 СЛЕДУЮЩИЕ ШАГИ

1. Сохранить этот файл в новом репозитории
2. Создать ARCHITECTURE.md с диаграммами
3. Начать с Этапа 1: Подготовка
4. При работе с AI ассистентом указать на MIGRATION_PLAN.md для контекста

**Удачи в миграции! 🚀**
