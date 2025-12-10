# Создание нового Chat Backend

Chat Backend использует **Protocol + Registry** паттерн. Для добавления нового бекенда:

## 1. Создать папку с файлами бекенда

```
services/chat_backend/src/backends/
├── mybackend/
│   ├── __init__.py      # Экспорт класса
│   └── backend.py       # Реализация
```

## 2. Реализовать протокол ChatBackend (`backend.py`)

```python
from typing import AsyncIterator, Iterator
from backends.protocol import ChatBackend, StreamEvent, SourceInfo
from settings import settings
from logging_config import get_logger

logger = get_logger("alpaca.chat.mybackend")

class MyBackend(ChatBackend):
    """Мой кастомный бекенд."""
    
    def __init__(self):
        # Инициализация клиентов, подключений и т.д.
        pass
    
    @property
    def name(self) -> str:
        return "mybackend"
    
    async def stream(
        self, 
        query: str, 
        history: list[dict] | None = None
    ) -> AsyncIterator[StreamEvent]:
        """
        Основной метод — стриминг ответа.
        
        Args:
            query: Вопрос пользователя
            history: История сообщений [{"role": "user"|"assistant", "content": "..."}]
            
        Yields:
            StreamEvent с type="token"|"sources"|"error"|"done"
        """
        try:
            # 1. Поиск релевантных документов (RAG)
            sources = []  # List[SourceInfo]
            
            # 2. Генерация ответа (стриминг токенов)
            for token in self._generate_response(query, sources):
                yield StreamEvent(type="token", data=token)
            
            # 3. Отправить источники
            if sources:
                yield StreamEvent(
                    type="sources", 
                    data=[s.__dict__ for s in sources]
                )
            
            # 4. Завершение
            yield StreamEvent(type="done", data=None)
            
        except Exception as e:
            logger.error(f"❌ Ошибка генерации | error={e}")
            yield StreamEvent(type="error", data=str(e))
    
    def _generate_response(self, query: str, sources: list) -> Iterator[str]:
        """Логика генерации (заглушка)."""
        yield "Ответ от MyBackend"
```

## 3. Экспортировать класс (`__init__.py`)

```python
from .backend import MyBackend

__all__ = ["MyBackend"]
```

## 4. Зарегистрировать в реестре (`backends/__init__.py`)

```python
from backends.simple import SimpleChatBackend
from backends.agent import AgentChatBackend
from backends.mybackend import MyBackend  # Добавить импорт

BACKENDS: dict[str, type[ChatBackend]] = {
    "simple": SimpleChatBackend,
    "agent": AgentChatBackend,
    "mybackend": MyBackend,  # Добавить в реестр
}
```

## 5. Добавить ENV в docker-compose.yml

```yaml
chat-backend:
  environment:
    - CHAT_BACKEND=mybackend  # Переключиться на новый бекенд
    # Дополнительные настройки бекенда
    - MY_CUSTOM_SETTING=value
```

## 6. Добавить настройки в settings.py (если нужно)

```python
class Settings(BaseSettings):
    # ... существующие настройки
    MY_CUSTOM_SETTING: str = "default"
```

---

## Справка по типам

### StreamEvent

| type | data | Описание |
|------|------|----------|
| `token` | `str` | Токен текста ответа |
| `sources` | `list[dict]` | Источники (file_path, content, score, metadata) |
| `error` | `str` | Сообщение об ошибке |
| `done` | `None` | Сигнал завершения стрима |

### SourceInfo

```python
@dataclass
class SourceInfo:
    file_path: str       # Путь к файлу
    content: str         # Фрагмент текста
    score: float         # Релевантность (0-1)
    metadata: dict       # Дополнительные данные (chunk_index, title и т.д.)
```

---

## Существующие бекенды

| Бекенд | ENV | Описание |
|--------|-----|----------|
| `simple` | `CHAT_BACKEND=simple` | RAG pipeline + Ollama (embedder → vector search → generate) |
| `agent` | `CHAT_BACKEND=agent` | LangChain Agent + MCP Server (инструменты через MCP) |
