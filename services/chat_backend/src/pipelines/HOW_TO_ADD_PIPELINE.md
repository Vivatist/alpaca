# Как добавить новый Pipeline

## Обзор

Pipelines отвечают за оркестрацию RAG-процесса: поиск контекста, формирование промпта, генерацию ответа.

## Шаги для добавления нового пайплайна

### 1. Создайте файл пайплайна

Создайте файл `pipelines/my_pipeline.py`:

```python
"""
My Custom Pipeline.

Описание особенностей пайплайна.
"""

from typing import List, Dict, Any, Optional
import uuid

from logging_config import get_logger
from llm import generate_response

from .base import BasePipeline

logger = get_logger("chat_backend.pipelines.my_pipeline")


class MyCustomPipeline(BasePipeline):
    """
    Кастомный пайплайн с особой логикой.
    """
    
    def __init__(self, searcher, **kwargs):
        self.searcher = searcher
        # Дополнительные параметры
    
    def build_prompt(self, query: str, chunks: List[Dict[str, Any]]) -> str:
        """Формирует prompt для LLM."""
        # Ваша логика формирования промпта
        pass
    
    def generate_answer(
        self,
        query: str,
        conversation_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Генерирует ответ.
        
        Returns:
            Dict с обязательными полями:
            - answer: str
            - conversation_id: str
            - sources: List[Dict]
        """
        # Ваша логика генерации
        pass


__all__ = ["MyCustomPipeline"]
```

### 2. Зарегистрируйте в `__init__.py`

```python
from .my_pipeline import MyCustomPipeline

PIPELINES: Dict[str, Type[BasePipeline]] = {
    "simple": SimpleRAGPipeline,
    "my_pipeline": MyCustomPipeline,  # <-- Добавьте сюда
}
```

### 3. Обновите build_pipeline() если нужны особые зависимости

```python
def build_pipeline(...) -> BasePipeline:
    ...
    if backend == "my_pipeline":
        # Особая инициализация
        return MyCustomPipeline(
            searcher=searcher,
            extra_param=value
        )
    ...
```

### 4. Настройте через settings

Добавьте в `settings.py`:
```python
PIPELINE_TYPE: str = "my_pipeline"
```

Или через переменную окружения:
```
PIPELINE_TYPE=my_pipeline
```

## Примеры пайплайнов для реализации

### ConversationalPipeline
С поддержкой истории диалога:
- Сохранение истории в БД/Redis
- Передача контекста предыдущих сообщений в промпт

### RerankingPipeline  
С переранжированием результатов:
- Первичный поиск top_k * 3 чанков
- Reranker модель для уточнения релевантности
- Возврат top_k наиболее релевантных

### HybridPipeline
Гибридный поиск:
- Векторный поиск через embeddings
- Ключевой поиск через BM25/FTS
- Объединение результатов

### AgentPipeline
С агентным подходом:
- Анализ вопроса и выбор стратегии
- Несколько итераций поиска при необходимости
- Самопроверка ответа

## Структура ответа

Все пайплайны должны возвращать Dict с полями:

```python
{
    "answer": str,           # Обязательно: текст ответа
    "conversation_id": str,  # Обязательно: UUID разговора
    "sources": [             # Обязательно: список источников
        {
            "file_path": str,
            "chunk_index": int,
            "similarity": float,
        }
    ],
    # Опционально: дополнительные поля
    "metadata": {...},
}
```
