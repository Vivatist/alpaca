# Chat Backend Service

REST API для чата с RAG-системой ALPACA. Поддерживает два режима работы: простой RAG и агентский с LangChain.

## Архитектура

```
backends/
├── simple/      # Простой RAG: поиск → промпт → LLM
│   ├── backend.py
│   ├── embedder.py
│   ├── searcher.py
│   ├── pipeline.py
│   └── ollama.py
└── agent/       # Агент LangChain с MCP-инструментом поиска
    ├── backend.py
    ├── langchain.py
    └── mcp.py
```

Выбор бэкенда через ENV: `CHAT_BACKEND=simple` или `CHAT_BACKEND=agent`

## Запуск

```bash
cd /home/alpaca/alpaca/services
docker compose up chat-backend -d
```

## API Endpoints

- `GET /health` — Health check
- `GET /api/chat/stats` — Статистика базы (чанки, файлы)
- `POST /api/chat` — SSE-стриминг ответа
- `GET /api/files/download` — Скачивание файла по пути

### Пример запроса (SSE streaming)

```bash
curl -N http://localhost:8082/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Найди договоры аренды"}'
```

### SSE события

- `tool_call` — Агент вызывает инструмент (только agent backend)
- `metadata` — Источники и conversation_id
- `chunk` — Часть ответа
- `done` — Завершение
- `error` — Ошибка

## Тесты

```bash
cd services/chat_backend
pytest
```

## Конфигурация (ENV)

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `CHAT_BACKEND` | `simple` или `agent` | `simple` |
| `RAG_TOP_K` | Количество чанков для контекста | `5` |
| `RAG_SIMILARITY_THRESHOLD` | Порог релевантности | `0.3` |
| `OLLAMA_BASE_URL` | URL Ollama | `http://ollama:11434` |
| `OLLAMA_LLM_MODEL` | Модель LLM | `qwen2.5:32b` |
| `OLLAMA_EMBEDDING_MODEL` | Модель эмбеддингов | `bge-m3` |
