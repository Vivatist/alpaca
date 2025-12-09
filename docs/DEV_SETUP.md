# Развёртывание рабочего места разработчика ALPACA

## Архитектура разработки

**Ollama всегда работает на сервере** с GPU (RTX 3090). Локально Ollama не запускается — используется удалённый сервер через Tailscale.

Локальная разработка использует два Docker Compose:
- **alpaca** (`services/docker-compose.yml`) — основные микросервисы ALPACA
- **supabase** (`~/supabase/docker`) — только база данных PostgreSQL + pgvector

> Supabase — это чисто база данных. Там меняем только схемы: таблицы и поддержка векторов.

## Требования

- Docker Desktop
- Git
- Tailscale (для доступа к удалённой Ollama)
- VS Code (рекомендуется)

## 1. Клонирование репозитория

```bash
git clone https://github.com/Vivatist/alpaca.git
cd alpaca
```

## 2. Установка Supabase

```bash
cd alpaca/scripts/setup_supabase

# Если нужно, дать права на запуск
chmod +x setup_supabase.sh

./setup_supabase.sh
```

Скрипт автоматически:
- Клонирует Supabase в `~/supabase/docker`
- Генерирует безопасные пароли
- Создаёт схему БД (таблицы `files` и `chunks`)
- Запускает контейнеры

(если что-то пошло не так, чтобы заново не скачивать supabase, запустите `./reset_supabase.sh` после этого можно повторить установку - пароли сгенерируются заново, схемы применятся. Скачивания не будет.)

**Supabase Studio**: http://localhost:8000
- User: `supabase`
- Password: см. `DASHBOARD_PASSWORD` в `~/supabase/docker/.env`

## 3. Настройка окружения

Создать/отредактировать `services/.env`:

```env
# Database - локальный Supabase
DATABASE_URL=postgresql://postgres:YOUR_POSTGRES_PASSWORD@172.17.0.1:54322/postgres

# Ollama - удалённый сервер через Tailscale
OLLAMA_BASE_URL=http://100.68.201.91:11434
```

> **YOUR_POSTGRES_PASSWORD** — см. `POSTGRES_PASSWORD` в `~/supabase/docker/.env`

> **Примечание**: `172.17.0.1` — IP хоста из Docker-контейнера (bridge gateway)

## 4. Отслеживаемая папка

FileWatcher сканирует папку с документами для индексации. По умолчанию: `~/monitored_folder`

```bash
# Создать папку
mkdir -p ~/monitored_folder

# Скопировать тестовые документы (опционально)
cp -r /path/to/your/documents/* ~/monitored_folder/
```

Путь можно изменить в `docker-compose.yml`:
```yaml
volumes:
  - ~/monitored_folder:/monitored_folder
```

## 5. Запуск сервисов

```bash
cd alpaca/services
docker compose up -d
```

## 6. Проверка

```bash
# Health checks
curl http://localhost:8080/health  # Admin Backend
curl http://localhost:8082/health  # Chat Backend
curl http://localhost:8081/health  # FileWatcher

# Dashboard
curl http://localhost:8080/api/dashboard
```

## Порты сервисов

| Сервис | Порт | Описание |
|--------|------|----------|
| Supabase Studio | 8000 | UI управления БД |
| PostgreSQL | 54322 | База данных |
| Admin Backend | 8080 | Мониторинг и управление |
| FileWatcher | 8081 | Очередь файлов |
| Chat Backend | 8082 | RAG API для чата |
| MCP Server | 8083 | Model Context Protocol |

## Полезные команды

```bash
# Логи сервиса
docker compose logs -f chat-backend

# Перезапуск одного сервиса
docker compose up -d --build admin-backend

# Остановка всех сервисов
docker compose down

# Статус контейнеров
docker ps
```

