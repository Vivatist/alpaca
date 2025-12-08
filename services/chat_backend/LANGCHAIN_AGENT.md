# LangChain Agent RAG

Модуль агентского RAG со стримингом через LangChain и MCP-сервер.

## Описание

Агентский RAG отличается от простого RAG тем, что:
- **Простой RAG**: query → search → prompt → LLM → answer
- **Агентский RAG**: query → LLM (агент) → [решает использовать tools] → search (MCP) → LLM → answer

Агент сам решает, нужно ли использовать инструмент поиска, и может вызывать его несколько раз.

## Установка

```bash
# Базовые зависимости уже установлены
# Для LangChain Agent:
pip install -r requirements-langchain.txt
```

Или вручную:
```bash
pip install langchain-ollama langgraph langchain-core httpx
```

## Переключение между режимами

### Через ENV (docker-compose.yml)

```yaml
environment:
  - LLM_BACKEND=ollama             # Обычный RAG (по умолчанию)
  # - LLM_BACKEND=langchain_agent  # Агентский RAG
  - MCP_SERVER_URL=http://localhost:8083  # URL MCP-сервера для поиска
```

### Программно

```python
# Обычный режим (default)
from llm import generate_response, generate_response_stream

# Явно агентский режим
from llm.langchain_agent import generate_response, generate_response_stream
```

## Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                        API Layer                            │
│  chat.py: prepare_context() + generate_response[_stream]()  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      llm/__init__.py                        │
│  LLM_BACKEND → ollama | langchain_agent                     │
│  generate_response() / generate_response_stream()           │
└─────────────────────────────────────────────────────────────┘
                    │                       │
                    ▼                       ▼
┌─────────────────────────┐   ┌─────────────────────────────┐
│      llm/ollama.py      │   │   llm/langchain_agent.py    │
│  Direct HTTP to Ollama  │   │  LangChain + LangGraph      │
│                         │   │  ReAct Agent with Tools     │
└─────────────────────────┘   └─────────────────────────────┘
                                            │
                                            ▼
                              ┌─────────────────────────────┐
                              │    search_documents tool    │
                              │  HTTP → MCP Server (8083)   │
                              └─────────────────────────────┘
                                            │
                                            ▼
                              ┌─────────────────────────────┐
                              │       MCP Server            │
                              │  /tools/search_documents    │
                              │  Embedder + VectorSearcher  │
                              └─────────────────────────────┘
```

## MCP-сервер

Агент использует MCP-сервер для поиска документов. MCP-сервер работает в том же контейнере `chat-backend` на порту 8083.

### Настройка MCP_SERVER_URL

```yaml
# docker-compose.yml
environment:
  - MCP_SERVER_URL=http://localhost:8083
```

По умолчанию: `http://localhost:8083`

### API MCP-сервера

```bash
# Поиск документов
POST /tools/search_documents
{
  "query": "договор аренды",
  "top_k": 5
}

# Список инструментов
GET /tools
```

## Тестирование

### Внутри Docker

```bash
# Запустить тест (MCP-сервер должен быть доступен)
docker exec -it alpaca-chat-backend-1 python /app/src/test_langchain_agent.py
```

### Локально

```bash
cd services/chat_backend/src

# 1. Запустить MCP-сервер
python mcp_server.py &

# 2. Запустить тест
MCP_SERVER_URL=http://localhost:8083 \
OLLAMA_BASE_URL=http://localhost:11434 \
python test_langchain_agent.py
```

## Особенности стриминга

В агентском режиме стриминг работает иначе:
1. Агент думает и принимает решения (не стримится)
2. Если вызывает tool — HTTP запрос к MCP → ждём результат
3. Финальный ответ стримится токен за токеном

## Ограничения

- Требует дополнительные зависимости (~100MB)
- Медленнее из-за цикла "думать → действовать → наблюдать"
- Не все модели хорошо работают как агенты (рекомендуется qwen2.5:32b+)
- Требует работающий MCP-сервер

## TODO

- [ ] Добавить больше инструментов (калькулятор, текущая дата)
- [ ] Кэширование результатов поиска в рамках сессии
- [ ] Streaming промежуточных шагов агента
- [ ] Ограничение количества итераций агента
