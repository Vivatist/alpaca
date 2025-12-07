# Searchers для Chat Backend

Модуль для поиска релевантных документов.

## Доступные searchers

- **vector** - поиск через pgvector по косинусной близости эмбеддингов

## Добавление нового searcher'а

1. Создайте файл `my_searcher.py` в папке `searchers/`
2. Реализуйте класс с методом `search(query, **kwargs) -> List[Dict]`
3. Добавьте в `SEARCHERS` реестр в `__init__.py`

## Пример использования

```python
from searchers import build_searcher
from embedders import build_embedder
from repository import ChatRepository

embedder = build_embedder()
repo = ChatRepository(settings.DATABASE_URL)
searcher = build_searcher(embedder, repo)

results = searcher.search("мой запрос", top_k=5, threshold=0.3)
```
