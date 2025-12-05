# LangChain Agent RAG

Тестовый модуль агентского RAG со стримингом через LangChain.

## Описание

Агентский RAG отличается от простого RAG тем, что:
- **Простой RAG**: query → search → prompt → LLM → answer
- **Агентский RAG**: query → LLM (агент) → [решает использовать tools] → search → LLM → answer

Агент сам решает, нужно ли использовать инструмент поиска, и может вызывать его несколько раз.

## Установка

```bash
# Базовые зависимости уже установлены
# Для LangChain Agent:
pip install -r requirements-langchain.txt
```

Или вручную:
```bash
pip install langchain-ollama langgraph langchain-core
```

## Переключение между режимами

### Через ENV (docker-compose.yml)

```yaml
environment:
  - LLM_BACKEND=ollama          # Обычный RAG (по умолчанию)
  # - LLM_BACKEND=langchain_agent  # Агентский RAG
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
                              │  Uses injected search_func  │
                              └─────────────────────────────┘
```

## Инъекция зависимостей

Агент получает функцию поиска через `set_search_function()`:

```python
from llm.langchain_agent import set_search_function

# Регистрируется автоматически при создании pipeline
# если LLM_BACKEND=langchain_agent
set_search_function(searcher.search)
```

## Тестирование

### Внутри Docker

```bash
# Установить зависимости
docker exec -it alpaca-chat-backend-1 pip install langchain-ollama langgraph langchain-core

# Запустить тест
docker exec -it alpaca-chat-backend-1 python /app/src/test_langchain_agent.py
```

### Локально

```bash
cd services/chat_backend/src
pip install -r ../requirements-langchain.txt
OLLAMA_BASE_URL=http://localhost:11434 python test_langchain_agent.py
```

## Особенности стриминга

В агентском режиме стриминг работает иначе:
1. Агент думает и принимает решения (не стримится)
2. Если вызывает tool — ждём результат
3. Финальный ответ стримится токен за токеном

## Ограничения

- Требует дополнительные зависимости (~100MB)
- Медленнее из-за цикла "думать → действовать → наблюдать"
- Не все модели хорошо работают как агенты (рекомендуется qwen2.5:32b+)

## TODO

- [ ] Добавить больше инструментов (калькулятор, текущая дата)
- [ ] Кэширование результатов поиска в рамках сессии
- [ ] Streaming промежуточных шагов агента
- [ ] Ограничение количества итераций агента
