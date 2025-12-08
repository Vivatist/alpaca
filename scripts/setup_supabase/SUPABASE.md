# Установка Supabase и развёртывание схемы БД

Supabase устанавливается **отдельно** от основного проекта в `~/supabase/` и работает на порту **54322** (не стандартный 5432).

## Быстрая установка (автоматическая)

```bash
cd ~/alpaca/scripts/setup_supabase
./setup_supabase.sh
```

Скрипт автоматически:
- Клонирует Supabase в `~/supabase/`
- Настроит `.env` с секретами
- Изменит порт PostgreSQL на 54322
- Подключит к сети `alpaca_network`
- Запустит все сервисы
- Применит схему БД

---

## Ручная установка

### 1. Клонирование Supabase

```bash
cd ~/
git clone --depth 1 https://github.com/supabase/supabase
cd supabase/docker
cp .env.example .env
```

### 2. Настройка .env

Отредактируйте `~/supabase/docker/.env`:

```bash
# Обязательно измените!
POSTGRES_PASSWORD=your-secure-password-here

# Сгенерируйте JWT секрет
JWT_SECRET=$(openssl rand -base64 32)
```

### 3. Изменение порта PostgreSQL (рекомендуется)

По умолчанию Supabase использует порт 5432, что может конфликтовать с локальным PostgreSQL.

Создайте файл `docker-compose.override.yml`:

```yaml
services:
  db:
    ports:
      - "54322:5432"
```

### 4. Подключение к сети alpaca_network

Добавьте в `docker-compose.override.yml`:

```yaml
networks:
  default:
    name: alpaca_network
    external: true
```

Создайте сеть если её нет:

```bash
docker network create alpaca_network
```

### 5. Запуск Supabase

```bash
cd ~/supabase/docker
docker compose up -d
```

Проверка:
```bash
docker compose ps
# Все сервисы должны быть healthy
```

---

## Развёртывание схемы БД

После запуска Supabase нужно создать таблицы `files` и `chunks`.

### Вариант 1: Через Supabase Studio (UI)

1. Откройте http://localhost:8000
2. Перейдите в SQL Editor
3. Выполните содержимое файлов:
   - `scripts/setup_supabase/schema_files.sql`
   - `scripts/setup_supabase/schema_chunks.sql`

### Вариант 2: Через psql

```bash
# Подключение к БД
PGPASSWORD=your-password psql -h localhost -p 54322 -U postgres -d postgres

# Или через docker
docker exec -i supabase-db psql -U postgres -d postgres
```

Выполните SQL:

```bash
# Таблица files (отслеживание файлов)
psql -h localhost -p 54322 -U postgres -d postgres \
  -f ~/alpaca/scripts/setup_supabase/schema_files.sql

# Таблица chunks (векторное хранилище)
psql -h localhost -p 54322 -U postgres -d postgres \
  -f ~/alpaca/scripts/setup_supabase/schema_chunks.sql
```

### Вариант 3: Одной командой

```bash
cd ~/alpaca/scripts/setup_supabase
PGPASSWORD=your-password psql -h localhost -p 54322 -U postgres -d postgres \
  -f schema_files.sql -f schema_chunks.sql
```

---

## Проверка установки

### Проверка таблиц

```sql
-- В psql или Supabase Studio
\dt public.*
-- Должны быть: files, chunks

-- Проверка pgvector
SELECT * FROM pg_extension WHERE extname = 'vector';
```

### Проверка подключения из сервисов

```bash
# DATABASE_URL для docker-compose.yml
DATABASE_URL=postgresql://postgres:your-password@db:5432/postgres

# DATABASE_URL для локальной разработки
DATABASE_URL=postgresql://postgres:your-password@localhost:54322/postgres
```

---

## Схема базы данных

### Таблица `files`

Отслеживание состояния файлов в `monitored_folder/`:

| Колонка | Тип | Описание |
|---------|-----|----------|
| `id` | serial | Primary key |
| `path` | text | Путь к файлу (уникальный) |
| `hash` | text | SHA256 хэш содержимого |
| `size` | bigint | Размер файла |
| `mtime` | float | Время модификации |
| `status_sync` | enum | `ok`, `added`, `updated`, `deleted`, `processed`, `error` |
| `last_checked` | timestamp | Время последней проверки |

### Таблица `chunks`

Векторное хранилище для RAG:

| Колонка | Тип | Описание |
|---------|-----|----------|
| `id` | bigserial | Primary key |
| `content` | text | Текст чанка |
| `embedding` | vector(1024) | Вектор для bge-m3 |
| `metadata` | jsonb | file_hash, file_path, chunk_index, title, summary и др. |

### Функция `match_chunks`

Векторный поиск с фильтрацией:

```sql
SELECT * FROM match_chunks(
    query_embedding := '[0.1, 0.2, ...]'::vector,
    match_count := 5,
    filter := '{"category": "Договор"}'::jsonb
);
```

---

## Полезные команды

```bash
# Статус сервисов
cd ~/supabase/docker && docker compose ps

# Логи PostgreSQL
docker compose logs db -f

# Остановка
docker compose down

# Полная очистка (удалит данные!)
docker compose down -v
```

## Доступы

| Сервис | URL |
|--------|-----|
| Supabase Studio | http://localhost:8000 |
| PostgreSQL | localhost:54322 |
| API Gateway | http://localhost:8000 |
