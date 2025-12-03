# Chat Backend Service

REST API для чата с RAG-системой ALPACA.

## Разработка в контейнере (Dev Container)

### Запуск

1. Откройте VS Code в папке `services/chat_backend`
2. `Ctrl+Shift+P` → "Dev Containers: Reopen in Container"
3. VS Code пересоберёт контейнер и откроет терминал внутри

### Или вручную

```bash
cd /home/alpaca/alpaca/services
docker compose up chat-backend -d
```

## API Endpoints

- `GET /health` - Health check
- `GET /api/chat/hello` - Hello World
- `POST /api/chat/` - Отправить сообщение

### Пример запроса

```bash
curl -X POST http://localhost:8000/api/chat/ \
  -H "Content-Type: application/json" \
  -d '{"message": "Что такое RAG?"}'
```

## Тесты

```bash
# В контейнере
pytest

# Или локально
cd services/chat_backend
pytest
```

## TODO

- [ ] RAG pipeline (embedding → pgvector search → LLM)
- [ ] История диалогов
- [ ] Streaming ответов
- [ ] WebSocket для real-time
