# ALPACA RAG

> Монолитная RAG (Retrieval-Augmented Generation) система для управления корпоративными знаниями с автоматической обработкой документов

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🎯 Особенности

- **Автоматическое сканирование документов** - мониторинг папки с файлами, обнаружение изменений по SHA256 hash
- **Парсинг различных форматов** - PDF, DOCX, XLSX, PPTX, TXT через Unstructured API
- **Векторный поиск** - PostgreSQL + pgvector для быстрого семантического поиска
- **Локальные LLM** - Ollama с моделями qwen2.5:14b (генерация) и bge-m3 (embeddings)
- **Монолитная архитектура** - простота разработки, отладки и деплоя
- **REST API** - FastAPI с автоматической документацией
- **Фоновая обработка** - автоматическое чанкирование и индексирование документов

## 🏗️ Архитектура

```
Монолитное FastAPI приложение (Python 3.12, venv)
├── API endpoints (FastAPI)
├── Background workers (APScheduler)
├── Core business logic
└── Database layer (asyncpg)

Внешние сервисы (Docker)
├── Unstructured API - парсинг документов
├── Ollama - LLM и embeddings (GPU)
├── Admin Backend - мониторинг
└── Supabase - PostgreSQL + pgvector
```

**Подробности:** [ARCHITECTURE.md](ARCHITECTURE.md)

## 📋 Требования

- Python 3.12+
- Docker и Docker Compose
- PostgreSQL 15+ с расширением pgvector
- (Опционально) NVIDIA GPU для Ollama

## 🚀 Быстрый старт

### 1. Клонирование репозитория

```bash
git clone https://github.com/Vivatist/alpaca.git
cd alpaca
```

### 2. Настройка окружения

```bash
# Создать виртуальное окружение
python3.12 -m venv venv
source venv/bin/activate  # Linux/macOS
# или
venv\Scripts\activate  # Windows

# Установить зависимости
pip install -r requirements.txt
```

### 3. Конфигурация

```bash
# Скопировать пример конфигурации
cp .env.example .env

# Отредактировать .env
nano .env
```

**Обязательные параметры:**
- `DATABASE_URL` - PostgreSQL connection string от Supabase
- `MONITORED_PATH` - путь к папке с документами

### 4. Запуск внешних сервисов

```bash
cd docker
docker-compose up -d
```

Это запустит:
- Unstructured API (порт 9000)
- Ollama (порт 11434)
- Admin Backend (порт 8080)

### 5. Загрузка моделей Ollama

```bash
# Подключиться к контейнеру
docker exec -it alpaca-rag-ollama-1 bash

# Загрузить модели
ollama pull bge-m3
ollama pull qwen2.5:14b

# Проверить
ollama list
```

### 6. Инициализация базы данных

```bash
# Применить миграции
alembic upgrade head
```

### 7. Запуск приложения

```bash
# Development режим (с hot reload)
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Production режим
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 8. Проверка работы

Откройте в браузере:
- API документация: http://localhost:8000/docs
- Admin панель: http://localhost:8080
- Healthcheck: http://localhost:8000/health

## 📁 Структура проекта

```
alpaca/
├── app/                    # Основное приложение
│   ├── api/               # FastAPI endpoints
│   ├── core/              # Бизнес-логика
│   ├── db/                # Database layer
│   ├── workers/           # Background tasks
│   └── utils/             # Утилиты
├── docker/                # Docker конфигурация
├── tests/                 # Тесты
├── scripts/               # Скрипты
├── settings.py            # Централизованная конфигурация
├── main.py                # Точка входа
├── requirements.txt       # Зависимости
└── pyproject.toml         # Метаданные проекта
```

## 🔧 Конфигурация

Все настройки через переменные окружения в `.env` файле:

### Мониторинг файлов
```env
MONITORED_PATH=/path/to/documents
SCAN_INTERVAL=20
ALLOWED_EXTENSIONS=[".docx", ".pdf", ".txt", ".xlsx", ".pptx"]
```

### RAG настройки
```env
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
TOP_K_RESULTS=5
SIMILARITY_THRESHOLD=0.7
```

### Модели
```env
OLLAMA_EMBED_MODEL=bge-m3
OLLAMA_LLM_MODEL=qwen2.5:14b
```

**Полный список:** [.env.example](.env.example)

## 🔄 Workflow обработки документов

1. **File Watcher** сканирует `MONITORED_PATH` каждые 20 секунд
2. Определяет изменения файлов по SHA256 hash
3. Обновляет статусы в таблице `file_state`
4. **File Processor** берёт файлы со статусом `added` или `updated`
5. Парсит документ через Unstructured API
6. Разбивает текст на чанки (1000 символов, overlap 200)
7. Генерирует embeddings через Ollama (bge-m3)
8. Сохраняет чанки в таблицу `documents`
9. Обновляет статус на `ok`

## 📊 База данных

### file_state - метаданные файлов
```sql
CREATE TABLE file_state (
    id SERIAL PRIMARY KEY,
    file_path TEXT NOT NULL UNIQUE,
    file_size BIGINT,
    file_hash TEXT,
    file_mtime DOUBLE PRECISION,
    status_sync TEXT DEFAULT 'ok',
    last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Статусы:**
- `ok` - обработан успешно
- `added` - новый файл
- `updated` - изменён
- `processed` - в обработке
- `error` - ошибка

### documents - векторные чанки
```sql
CREATE TABLE documents (
    id BIGSERIAL PRIMARY KEY,
    file_hash TEXT NOT NULL,
    file_path TEXT,
    chunk_index INTEGER,
    chunk_text TEXT,
    embedding VECTOR(1024),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 🧪 Тестирование

```bash
# Запуск всех тестов
pytest

# С покрытием
pytest --cov=app --cov-report=html

# Конкретный файл
pytest tests/test_parser.py -v
```

## 🔍 Мониторинг

### Через Admin Backend

```bash
# Открыть в браузере
http://localhost:8080/api/dashboard
```

### Через API

```bash
# Статистика файлов
curl http://localhost:8000/api/admin/file-state/stats

# Последние обработанные документы
curl http://localhost:8000/api/documents?limit=10
```

### Логи

```bash
# Development
tail -f logs/alpaca.log

# Production (systemd)
journalctl -u alpaca-rag -f
```

## 🐛 Troubleshooting

### Ollama не отвечает
```bash
# Проверить статус
docker ps | grep ollama

# Проверить модели
curl http://localhost:11434/api/tags
```

### Unstructured timeout
```bash
# Увеличить в .env
UNSTRUCTURED_TIMEOUT=600

# Проверить размер файла
ls -lh /path/to/file
```

### Ошибки pgvector
```sql
-- Включить расширение
CREATE EXTENSION IF NOT EXISTS vector;

-- Проверить таблицы
\dt
```

## 📚 API Документация

После запуска приложения:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI schema: http://localhost:8000/openapi.json

## 🤝 Разработка

### Установка dev зависимостей

```bash
pip install -r requirements.txt
pip install -e ".[dev]"
```

### Форматирование кода

```bash
# Black
black .

# Ruff
ruff check . --fix
```

### Type checking

```bash
mypy app/
```

## 📝 Миграция данных

Если у вас есть данные из старого проекта:

```bash
# Запустить скрипт миграции
python scripts/migrate_db.py \
  --old-db "postgresql://..." \
  --new-db "postgresql://..."
```

Подробности: [MIGRATION_PLAN.md](MIGRATION_PLAN.md)

## 🔐 Production deployment

### Systemd service

```bash
# Создать service файл
sudo nano /etc/systemd/system/alpaca-rag.service

# Перезагрузить и запустить
sudo systemctl daemon-reload
sudo systemctl enable alpaca-rag
sudo systemctl start alpaca-rag
```

### Nginx reverse proxy

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 📄 Лицензия

MIT License - см. [LICENSE](LICENSE)

## 👥 Авторы

Alpaca Team

## 🔗 Ссылки

- [FastAPI](https://fastapi.tiangolo.com/)
- [Ollama](https://ollama.ai/)
- [Unstructured](https://unstructured.io/)
- [pgvector](https://github.com/pgvector/pgvector)
- [Supabase](https://supabase.com/)

## 📞 Поддержка

При возникновении проблем создайте issue в GitHub.
