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
- VS Code (рекомендуется)

## 1. Подключение к сети разработки (Tailscale)

Ollama работает на удалённом сервере с GPU. Для доступа к нему используется VPN-сеть Tailscale.

### Установка Tailscale

1. Скачайте и установите Tailscale: https://tailscale.com/download
2. Запустите и авторизуйтесь через Google/GitHub

### Принятие инвайта

Получите ссылку-инвайт от администратора проекта и перейдите по ней. После принятия ваше устройство появится в сети `alpaca`.

### Проверка доступности Ollama

```bash
# Проверить подключение к Tailscale
tailscale status

# Проверить доступность Ollama на сервере
curl http://100.68.201.91:11434/api/tags
```

Ожидаемый ответ — список моделей:
```json
{"models":[{"name":"qwen2.5:32b",...},{"name":"bge-m3:latest",...}]}
```

> **Если не работает**: убедитесь, что Tailscale подключён (иконка в трее зелёная) и вы приняли инвайт в сеть.

## 2. Клонирование репозитория

```bash
git clone https://github.com/Vivatist/alpaca.git
cd alpaca
```

## 3. Установка Supabase

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

## 4. Настройка окружения

Создать/отредактировать `services/.env`:

```env
# Database - локальный Supabase
DATABASE_URL=postgresql://postgres:YOUR_POSTGRES_PASSWORD@172.17.0.1:54322/postgres

# Ollama - удалённый сервер через Tailscale
OLLAMA_BASE_URL=http://100.68.201.91:11434
```

> **YOUR_POSTGRES_PASSWORD** — см. `POSTGRES_PASSWORD` в `~/supabase/docker/.env`

> **Примечание**: `172.17.0.1` — IP хоста из Docker-контейнера (bridge gateway)

## 5. Отслеживаемая папка

FileWatcher сканирует папку с документами для индексации. По умолчанию: `alpaca/monitored_folder` (рядом с `services/`).

```bash
# Создать папку (из корня репозитория)
mkdir -p monitored_folder

# Скопировать тестовые документы (опционально)
cp -r /path/to/your/documents/* monitored_folder/
```

> **Примечание**: Если папка не существует, Docker создаст её автоматически при запуске, но лучше создать заранее.

Путь можно изменить в `docker-compose.yml`:
```yaml
volumes:
  - ~/monitored_folder:/monitored_folder
```

## 6. Запуск сервисов

```bash
cd alpaca/services
docker compose up -d
```

## 7. Проверка

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

## CI/CD и деплой

### Автоматический деплой (GitHub Actions)

При push в `main` автоматически запускается workflow:

1. **Определение изменений** — проверяется какие сервисы изменились
2. **Build** — сборка Docker-образов изменённых сервисов
3. **Push** — загрузка образов в GitHub Container Registry (`ghcr.io`)
4. **Deploy** — обновление на сервере через self-hosted runner

**Триггеры:**
- Push в `main` с изменениями в `services/`
- Ручной запуск через GitHub Actions UI

### Ручной деплой конкретного сервиса

В GitHub → Actions → "Build and Deploy" → Run workflow:
- Выбрать сервис: `all` / `admin-backend` / `ingest` / `chat-backend` / `mcp-server` / `filewatcher`

### Self-hosted runner

Деплой выполняется на GPU-сервере через self-hosted runner `alpaca-phantom`.

**Проверка статуса runner:**
GitHub → Settings → Actions → Runners

**Если runner офлайн** — на сервере:
```bash
cd ~/actions-runner
./run.sh  # или sudo systemctl restart actions-runner
```

### Внешний доступ к API

После деплоя API доступен через VDS:

| Сервис | URL |
|--------|-----|
| Admin Backend | `https://api.alpaca-smart.com:8443/admin/` |
| Chat Backend | `https://api.alpaca-smart.com:8443/chat/` |

Архитектура: `Интернет → VDS (nginx) → SSH tunnel → GPU Server`

