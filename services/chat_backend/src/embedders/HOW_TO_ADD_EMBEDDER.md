# Embedder для Chat Backend

Модуль для создания векторных представлений текста через Ollama API.

## Использование

```python
from embedders import build_embedder

embedder = build_embedder()
vector = embedder("текст для эмбеддинга")
# vector: List[float] с размерностью 1024 (для bge-m3)
```

## Добавление нового эмбеддера

1. Создайте файл `my_embedder.py` в папке `embedders/`
2. Реализуйте функцию с сигнатурой `(text: str) -> List[float]`
3. Добавьте в `EMBEDDERS` реестр в `__init__.py`
4. Добавьте настройку `EMBEDDER_BACKEND` в `settings.py`
