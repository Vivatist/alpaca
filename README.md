# ALPACA RAG

## Подготовка внешних сервисов

### 1. Supabase (PostgreSQL + pgvector)

1. Создайте проект на https://supabase.com
2. В проекте перейдите: **Settings** → **Database**
3. Найдите раздел **Connection string** → **URI mode**
4. Скопируйте строку вида:
   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.xxxxx.supabase.co:5432/postgres
   ```
5. Включите **pgvector** расширение:
   - Откройте SQL Editor в Supabase
   - Выполните:
     ```sql
     CREATE EXTENSION IF NOT EXISTS vector;
     ```

### 2. Docker сервисы (Ollama + Unstructured)

```bash
chmod +x scripts/start_services.sh
./scripts/start_services.sh
```

Это запустит:
- **Ollama** (http://localhost:11434) - для LLM и embeddings
- **Unstructured** (http://localhost:9000) - для парсинга документов

### 3. Настройка .env

```bash
cp .env.example .env
nano .env
```

Укажите ваш Supabase DATABASE_URL:
```env
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@db.xxxxx.supabase.co:5432/postgres
```

## Проверка

```bash
# Проверка Ollama
curl http://localhost:11434/api/tags

# Проверка Unstructured
curl http://localhost:9000/general/v0/general

# Проверка Supabase
source venv/bin/activate
python -c "from settings import settings; print(settings.DATABASE_URL)"
```

## Готово!

Все внешние сервисы настроены. Можно переходить к разработке.
