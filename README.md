# ALPACA RAG

Система обработки документов с RAG (Retrieval Augmented Generation).

## Быстрый старт

### 1. Установка Supabase

Supabase устанавливается **отдельно** от основного проекта.

📖 Подробная инструкция: [SUPABASE_SETUP.md](SUPABASE_SETUP.md)

**Быстрая установка (Self-Hosted):**

```bash
cd ~/
git clone --depth 1 https://github.com/supabase/supabase
cd supabase/docker
cp .env.example .env
# Отредактируйте .env (установите пароли и секреты)
docker compose up -d
```

Supabase будет доступен на http://localhost:8000

### 2. Запуск сервисов проекта

```bash
cd ~/alpaca

# Настройте переменные окружения
cp .env.example .env
# Отредактируйте .env и укажите DATABASE_URL от Supabase

# Запуск Docker сервисов
cd services
docker compose up -d
```

Это запустит:
- **Ollama** (http://localhost:11434) - LLM qwen2.5:32b + embeddings bge-m3 (GPU)
- **Unstructured** (http://localhost:9000) - парсинг документов
- **File Watcher** (http://localhost:8081) - мониторинг файлов + API
- **Admin Backend** (http://localhost:8080) - REST API для управления

### 3. Проверка

```bash
# Проверка Ollama
curl http://localhost:11434/api/tags

# Проверка Unstructured
curl http://localhost:9000/general/v0/general

# Проверка подключения к Supabase
source venv/bin/activate
python -c "from settings import settings; print(settings.DATABASE_URL)"
```

## Архитектура

- **Supabase** - PostgreSQL + pgvector (отдельная установка)
- **Ollama** - LLM и embeddings (Docker + GPU)
- **Unstructured** - парсинг документов (Docker)
- **File Watcher** - мониторинг файлов с REST API (Docker)
- **Admin Backend** - REST API для управления (Docker)
- **Worker** - обработка очереди файлов (Python процесс)

## Поддерживаемые форматы документов

- **DOC/DOCX** — MarkItDown + python-docx + OCR изображений
- **PDF** — PyMuPDF + локальный/Unstructured OCR
- **PPT/PPTX** — python-pptx с конвертацией `.ppt -> .pptx` + Unstructured fallback
- **XLS/XLSX** — openpyxl с автораспознаванием шапок, `.xls -> .xlsx` через LibreOffice
- **TXT** — автоопределение кодировки и нормализация Markdown

## Запуск Worker

```bash
# В отдельном терминале
source venv/bin/activate
python main.py
```

## Остановка сервисов

```bash
# Остановка Docker контейнеров
cd services
docker compose down

# Остановка Supabase (в его директории)
cd ~/supabase/docker
docker compose down
```
