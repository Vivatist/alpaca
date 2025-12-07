# Инструкции для GitHub Copilot

## Сетевое окружение проекта ALPACA

### Режим работы внутри Dev Container

При работе **изнутри контейнера** (режим Dev Container) сервисы доступны по именам в Docker сети `alpaca_network`:

| Сервис | Хост | Порт | Пример URL |
|--------|------|------|------------|
| PostgreSQL | `db` | `5432` | `postgresql://postgres:password@db:5432/postgres` |
| Ollama | `ollama` | `11434` | `http://ollama:11434` |

### Режим работы снаружи контейнера

При работе **снаружи контейнера** (с хост-машины) сервисы доступны через проброшенные порты на `localhost`:

| Сервис | Хост | Порт | Пример URL |
|--------|------|------|------------|
| PostgreSQL | `localhost` | `54322` | `postgresql://postgres:password@localhost:54322/postgres` |
| Ollama | `localhost` | `11434` | `http://localhost:11434` |

### Важно помнить

1. **НЕ использовать `localhost`** изнутри контейнера — это укажет на сам контейнер, а не на другие сервисы
2. **НЕ использовать `host.docker.internal`** — используй имена сервисов в сети Docker
3. Прокси настроен с `NO_PROXY` для локальных адресов — это позволяет обращаться к `db`, `ollama` и другим сервисам напрямую

### Проверка связи изнутри контейнера

```bash
# PostgreSQL
nc -zv db 5432

# Ollama
curl -s http://ollama:11434/api/version

# DNS резолвинг
getent hosts db ollama
```

### Структура сети

```
alpaca_network (172.18.0.0/16)
├── db (PostgreSQL + pgvector) - 172.18.0.20:5432
├── ollama - 172.18.0.22:11434
└── chat_backend (этот контейнер) - 172.18.0.21:8000
```
