# Deployment Guide

## Архитектура CI/CD

```
┌─────────────┐     push main     ┌─────────────────┐
│   Локально  │ ─────────────────▶│     GitHub      │
│  (Windows)  │                   │   Repository    │
└─────────────┘                   └────────┬────────┘
                                           │
                                           ▼
                                  ┌─────────────────┐
                                  │  GitHub Actions │
                                  │   (ubuntu-latest)│
                                  └────────┬────────┘
                                           │ build & push
                                           ▼
                                  ┌─────────────────┐
                                  │     ghcr.io     │
                                  │ Container Registry│
                                  └────────┬────────┘
                                           │
                                           ▼
┌─────────────────────────────────────────────────────┐
│              Сервер (alpaca-phantom)                │
│  ┌───────────────┐     pull      ┌──────────────┐  │
│  │ Self-hosted   │ ◀────────────▶│    Docker    │  │
│  │    Runner     │               │   Services   │  │
│  └───────────────┘               └──────────────┘  │
│                                                     │
│  ┌──────────────┐  ┌──────────────┐               │
│  │    Ollama    │  │   Supabase   │               │
│  │   (GPU)      │  │  (PostgreSQL)│               │
│  └──────────────┘  └──────────────┘               │
└─────────────────────────────────────────────────────┘
```

## Шаг 1: Настройка Self-hosted Runner на сервере

### 1.1. Создание runner в GitHub

1. Перейди в репозиторий на GitHub
2. Settings → Actions → Runners → New self-hosted runner
3. Выбери Linux x64
4. Скопируй команды установки

### 1.2. Установка на сервере

```bash
# SSH на сервер
ssh alpaca

# Создаём директорию для runner
mkdir -p ~/actions-runner && cd ~/actions-runner

# Скачиваем runner (версия может отличаться, смотри на GitHub)
curl -o actions-runner-linux-x64-2.311.0.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.311.0/actions-runner-linux-x64-2.311.0.tar.gz

tar xzf ./actions-runner-linux-x64-2.311.0.tar.gz

# Конфигурируем (токен из GitHub Settings → Actions → Runners)
./config.sh --url https://github.com/Vivatist/alpaca --token YOUR_TOKEN

# Устанавливаем как сервис
sudo ./svc.sh install
sudo ./svc.sh start

# Проверяем статус
sudo ./svc.sh status
```

### 1.3. Добавление runner в группу docker

```bash
sudo usermod -aG docker $USER
# Перелогиниться или:
newgrp docker
```

## Шаг 2: Настройка .env на сервере

Создай файл `/home/alpaca/alpaca/services/.env`:

```bash
# Database
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:54322/postgres

# Ollama (локальный на сервере)
OLLAMA_BASE_URL=http://localhost:11434

# Paths
MONITORED_FOLDER_PATH=/home/alpaca/monitored_folder
TMP_MD_PATH=/home/alpaca/tmp_md
```

## Шаг 3: Настройка GitHub Container Registry

Registry настраивается автоматически при первом push. Нужно только:

1. В GitHub Settings → Developer settings → Personal access tokens
2. Создать token с правами `write:packages`
3. Или использовать автоматический `GITHUB_TOKEN` (уже настроен в workflow)

### Сделать пакеты публичными (опционально)

По умолчанию пакеты приватные. Чтобы сделать публичными:
1. GitHub → Packages → alpaca-admin-backend → Package settings
2. Change visibility → Public

## Шаг 4: Первый деплой

### Ручной запуск workflow

1. GitHub → Actions → Build and Deploy
2. Run workflow → выбрать service: all
3. Дождаться завершения

### Проверка на сервере

```bash
ssh alpaca

# Проверить контейнеры
docker ps

# Проверить health
curl http://localhost:8080/health
curl http://localhost:8082/health

# Логи
cd ~/alpaca/services
docker compose logs -f admin-backend
```

## Автоматический деплой

После настройки runner, деплой происходит автоматически:

1. Пушишь в main локально
2. GitHub Actions определяет изменённые сервисы
3. Собирает только изменённые Docker images
4. Пушит в ghcr.io
5. Self-hosted runner на сервере:
   - Pull новых образов
   - Restart изменённых сервисов
   - Health check

## Команды для ручного управления

### На сервере

```bash
cd ~/alpaca/services

# Pull и restart всех сервисов
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Restart конкретного сервиса
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d admin-backend

# Откат к предыдущей версии
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull admin-backend:previous-sha
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d admin-backend

# Логи
docker compose logs -f --tail=100 admin-backend
```

### Локально

```bash
# Пуш в main (триггерит деплой)
git push origin main

# Ручной запуск workflow
gh workflow run deploy.yml -f service=admin-backend
```

## Troubleshooting

### Runner offline

```bash
# На сервере
cd ~/actions-runner
sudo ./svc.sh status
sudo ./svc.sh restart
```

### Build failed

Проверь логи в GitHub Actions. Частые причины:
- Синтаксическая ошибка в Dockerfile
- Отсутствует requirements.txt
- Нет доступа к базовому образу

### Deploy failed

```bash
# На сервере проверь логи runner
journalctl -u actions.runner.Vivatist-alpaca.* -f

# Проверь Docker
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs
```

### Контейнер не стартует

```bash
# Проверь .env
cat ~/alpaca/services/.env

# Проверь сеть
docker network ls
docker network inspect alpaca_network

# Проверь Supabase
docker ps | grep supabase
```

## Альтернативы Self-hosted Runner

### SSH Deploy (если runner не подходит)

Можно заменить job `deploy` на SSH:

```yaml
deploy:
  runs-on: ubuntu-latest
  steps:
    - name: Deploy via SSH
      uses: appleboy/ssh-action@v1
      with:
        host: ${{ secrets.SERVER_HOST }}
        username: ${{ secrets.SERVER_USER }}
        key: ${{ secrets.SSH_PRIVATE_KEY }}
        script: |
          cd ~/alpaca/services
          docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
          docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

Требует:
- Белый IP или reverse tunnel
- SSH ключ в GitHub Secrets
- Открытый SSH порт

### Watchtower (автоматический pull)

Установить Watchtower на сервере для автоматического обновления:

```yaml
# В docker-compose.yml на сервере
watchtower:
  image: containrrr/watchtower
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock
  environment:
    - WATCHTOWER_POLL_INTERVAL=300
    - WATCHTOWER_CLEANUP=true
```

Минус: нет контроля над временем деплоя.
