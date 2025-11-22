# Быстрый старт Alpaca RAG

## Предварительные требования

1. **Запущенные сервисы**:
   ```bash
   cd docker
   docker-compose up -d
   ```
   Это запустит:
   - Unstructured API (порт 8001)
   - Ollama (порт 11434)

2. **База данных PostgreSQL с pgvector** (Supabase или локальная)

3. **Модели Ollama**:
   ```bash
   ./scripts/init_models.sh
   ```

## Запуск приложения

### 1. Активировать виртуальное окружение
```bash
source venv/bin/activate
```

### 2. Настроить .env файл
Скопируйте `.env.example` в `.env` и заполните переменные:
```bash
cp .env.example .env
nano .env
```

Обязательные переменные:
- `DATABASE_URL` - PostgreSQL connection string
- `MONITORED_PATH` - путь к директории с документами
- `OLLAMA_BASE_URL` - URL Ollama API (по умолчанию http://localhost:11434)

### 3. Инициализировать базу данных
```bash
python -c "import asyncio; from app.db.connection import init_db; asyncio.run(init_db())"
```

### 4. Запустить FastAPI сервер
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

API будет доступен по адресу: http://localhost:8000

Документация API: http://localhost:8000/docs

### 5. Запустить Prefect server (в отдельном терминале)
```bash
source venv/bin/activate
prefect server start
```

Prefect UI: http://localhost:4200

### 6. Деплоить Prefect flows (в отдельном терминале)
```bash
source venv/bin/activate
python scripts/deploy_flows.py
```

### 7. Запустить Prefect worker (в отдельном терминале)
```bash
source venv/bin/activate
./scripts/start_prefect_worker.sh
```

## Проверка работоспособности

### Healthcheck всех компонентов
```bash
curl http://localhost:8000/api/admin/health
```

### Загрузить тестовый документ
```bash
curl -X POST "http://localhost:8000/api/documents/upload" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/path/to/document.pdf"
```

### Выполнить векторный поиск
```bash
curl -X POST "http://localhost:8000/api/search/vector" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "что такое машинное обучение?",
    "top_k": 5,
    "threshold": 0.7
  }'
```

### RAG запрос
```bash
curl -X POST "http://localhost:8000/api/search/rag" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "расскажи про deep learning",
    "top_k": 5
  }'
```

## Архитектура

```
┌─────────────────┐
│   FastAPI App   │ ← REST API endpoints
│   (port 8000)   │
└────────┬────────┘
         │
         ├─────► Documents API (/api/documents/*)
         ├─────► Search API (/api/search/*)
         └─────► Admin API (/api/admin/*)
                 
┌─────────────────┐
│ Prefect Server  │ ← Workflow orchestration
│   (port 4200)   │
└────────┬────────┘
         │
         └─────► Prefect Worker
                 │
                 ├─── file_watcher_flow (каждые 60 сек)
                 │    └─► сканирование директории
                 │
                 └─── process_document_flow
                      ├─► парсинг (Unstructured)
                      ├─► чанкинг (Langchain)
                      ├─► эмбеддинги (Ollama bge-m3)
                      └─► сохранение в БД (PostgreSQL)

┌─────────────────┐
│ External        │
│ Services        │
├─────────────────┤
│ Unstructured    │ ← Парсинг документов
│ (port 8001)     │
│                 │
│ Ollama          │ ← LLM + Embeddings
│ (port 11434)    │
│                 │
│ PostgreSQL      │ ← Векторная БД
│ + pgvector      │
└─────────────────┘
```

## API Endpoints

### Документы
- `GET /api/documents/` - список документов
- `GET /api/documents/{id}` - информация о документе
- `POST /api/documents/upload` - загрузить документ
- `DELETE /api/documents/{id}` - удалить документ
- `POST /api/documents/{id}/reprocess` - перезапустить обработку
- `GET /api/documents/{id}/chunks` - получить чанки документа

### Поиск и RAG
- `POST /api/search/vector` - векторный поиск по чанкам
- `POST /api/search/rag` - RAG запрос (поиск + генерация)
- `GET /api/search/stats` - статистика по базе
- `POST /api/search/similar-documents` - найти похожие документы

### Администрирование
- `GET /api/admin/health` - проверка компонентов
- `GET /api/admin/stats` - статистика системы
- `POST /api/admin/clear-failed` - удалить failed документы
- `POST /api/admin/reindex-all` - переиндексация всех документов
- `GET /api/admin/models` - список моделей Ollama
- `POST /api/admin/vacuum` - оптимизация БД

## Prefect Flows

### file_watcher_flow
- **Периодичность**: каждые 60 секунд
- **Задача**: Сканирование `MONITORED_PATH`, обнаружение новых/измененных файлов
- **Результат**: Добавление новых документов в очередь обработки

### process_document_flow
- **Триггер**: Новый файл обнаружен или загружен через API
- **Шаги**:
  1. `parse_document_task` - парсинг через Unstructured API
  2. `chunk_text_task` - разбивка на чанки (Langchain)
  3. `generate_embeddings_task` - генерация векторов (Ollama)
  4. `save_to_database_task` - сохранение в PostgreSQL
- **Retry**: 3 попытки с экспоненциальной задержкой

### process_queue_flow
- **Триггер**: Периодически или по событию
- **Задача**: Обработка очереди документов (статус = pending)
- **Параллелизм**: До 5 документов одновременно

## Мониторинг

1. **Prefect UI** (http://localhost:4200):
   - Статус flows и tasks
   - История выполнения
   - Логи и ошибки
   - Графы зависимостей

2. **FastAPI Docs** (http://localhost:8000/docs):
   - Интерактивная документация API
   - Тестирование endpoints

3. **Admin API**:
   - `/api/admin/health` - статус компонентов
   - `/api/admin/stats` - метрики системы

## Отладка

### Логи
```bash
# FastAPI логи
tail -f logs/alpaca.log

# Prefect worker логи
# Выводятся в stdout при запуске worker
```

### Проверка Prefect flows
```bash
source venv/bin/activate
python -c "from app.workers.scheduler import file_watcher_flow; file_watcher_flow()"
```

### Проверка обработки документа
```bash
source venv/bin/activate
python -c "
from app.workers.file_processor import process_document_flow
from app.db.models import FileState

file_state = FileState(path='/path/to/test.pdf', hash='test', state='new')
result = process_document_flow(file_state)
print(result)
"
```

## Производство

Для production деплоя:

1. Использовать PostgreSQL cluster с репликацией
2. Запустить несколько Prefect workers для параллелизма
3. Настроить reverse proxy (Nginx) перед FastAPI
4. Включить HTTPS
5. Настроить мониторинг (Prometheus + Grafana)
6. Использовать systemd для автозапуска сервисов

См. `ARCHITECTURE.md` для подробностей.
