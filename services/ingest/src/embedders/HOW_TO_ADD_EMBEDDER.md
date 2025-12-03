# Как добавить новый Embedder

## Структура модуля embedders

```
embedders/
├── __init__.py          ← реестр EMBEDDERS + build_embedder()
├── ollama.py            ← ollama_embedder() - через Ollama API
└── your_embedder.py     ← ваш новый эмбеддер
```

## Шаги

### 1. Создайте файл с эмбеддером

Создайте новый файл, например `openai.py`:

```python
"""
Описание: что делает этот эмбеддер.
"""

from typing import List, Dict, Any

from logging_config import get_logger
from contracts import FileSnapshot, Repository
from settings import settings

logger = get_logger("ingest.embedder.openai")


def openai_embedder(
    repo: Repository,
    file: FileSnapshot,
    chunks: List[str],
    doc_metadata: Dict[str, Any] = None
) -> int:
    """
    Создание эмбеддингов через OpenAI API.
    
    Args:
        repo: Репозиторий для работы с БД
        file: FileSnapshot с информацией о файле
        chunks: Список текстовых чанков
        doc_metadata: Метаданные документа
        
    Returns:
        Количество успешно сохранённых чанков
    """
    if not chunks:
        logger.warning(f"No chunks to embed | file={file.path}")
        return 0
    
    if doc_metadata is None:
        doc_metadata = {}
    
    # Удаляем старые чанки
    repo.delete_chunks_by_hash(file.hash)
    
    inserted_count = 0
    total_chunks = len(chunks)
    
    # Ваша логика получения эмбеддингов
    for idx, chunk_text in enumerate(chunks):
        try:
            # Получаем эмбеддинг (ваша реализация)
            embedding = get_openai_embedding(chunk_text)
            
            # Формируем метаданные
            metadata = {
                **doc_metadata,
                'file_hash': file.hash,
                'file_path': file.path,
                'chunk_index': idx,
                'total_chunks': total_chunks
            }
            
            # Сохраняем в БД
            repo.save_chunk(chunk_text, metadata, embedding)
            inserted_count += 1
            
        except Exception as e:
            logger.error(f"Error embedding chunk {idx}: {e}")
            continue
    
    logger.info(f"✅ Embedded {inserted_count}/{total_chunks} | file={file.path}")
    return inserted_count
```

### 2. Зарегистрируйте эмбеддер в `__init__.py`

Добавьте импорт и запись в словарь EMBEDDERS:

```python
# В начале файла добавьте импорт
from .openai import openai_embedder

# В словарь EMBEDDERS добавьте запись
EMBEDDERS: dict[str, Embedder] = {
    "ollama": ollama_embedder,
    "openai": openai_embedder,  # ← новый эмбеддер
}
```

### 3. Используйте эмбеддер

В `docker-compose.yml` установите переменную `EMBEDDER_BACKEND`:

```yaml
environment:
  EMBEDDER_BACKEND: "openai"
  # Добавьте необходимые переменные для вашего эмбеддера
  OPENAI_API_KEY: "sk-..."
```

## Правила написания эмбеддеров

1. **Сигнатура**: 
   ```python
   def embedder_name(
       repo: Repository,
       file: FileSnapshot,
       chunks: List[str],
       doc_metadata: Dict[str, Any] = None
   ) -> int
   ```

2. **Обязательные действия**:
   - Удалить старые чанки: `repo.delete_chunks_by_hash(file.hash)`
   - Сохранить новые чанки: `repo.save_chunk(text, metadata, embedding)`
   - Вернуть количество сохранённых чанков

3. **Метаданные чанка**:
   ```python
   metadata = {
       **doc_metadata,          # title, summary, keywords, extension
       'file_hash': file.hash,
       'file_path': file.path,
       'chunk_index': idx,
       'total_chunks': total_chunks
   }
   ```

4. **Обработка ошибок**: не бросайте исключения, логируйте ошибки

5. **Батчинг**: для производительности обрабатывайте чанки батчами

## Доступные настройки

```python
settings.OLLAMA_BASE_URL         # URL Ollama API
settings.OLLAMA_EMBEDDING_MODEL  # Модель для эмбеддингов
# Добавьте свои настройки в settings.py при необходимости
```

## Пример: эмбеддер с кэшированием

```python
# cached.py
"""
Эмбеддер с кэшированием в памяти для повторяющихся чанков.
"""

from typing import List, Dict, Any
import hashlib

from logging_config import get_logger
from contracts import FileSnapshot, Repository
from settings import settings
from .ollama import _get_embeddings_batch

logger = get_logger("ingest.embedder.cached")

# Простой кэш в памяти (для production используйте Redis)
_cache: Dict[str, List[float]] = {}


def _get_text_hash(text: str) -> str:
    """Хэш текста для кэширования."""
    return hashlib.md5(text.encode()).hexdigest()


def cached_embedder(
    repo: Repository,
    file: FileSnapshot,
    chunks: List[str],
    doc_metadata: Dict[str, Any] = None
) -> int:
    """Эмбеддер с кэшированием повторяющихся чанков."""
    if not chunks:
        return 0
    
    if doc_metadata is None:
        doc_metadata = {}
    
    repo.delete_chunks_by_hash(file.hash)
    
    inserted_count = 0
    total_chunks = len(chunks)
    
    # Разделяем на кэшированные и новые
    uncached_chunks = []
    uncached_indices = []
    
    for idx, chunk in enumerate(chunks):
        text_hash = _get_text_hash(chunk)
        if text_hash not in _cache:
            uncached_chunks.append(chunk)
            uncached_indices.append(idx)
    
    # Получаем эмбеддинги только для новых чанков
    if uncached_chunks:
        new_embeddings = _get_embeddings_batch(uncached_chunks)
        for chunk, embedding in zip(uncached_chunks, new_embeddings):
            _cache[_get_text_hash(chunk)] = embedding
    
    # Сохраняем все чанки
    for idx, chunk in enumerate(chunks):
        embedding = _cache.get(_get_text_hash(chunk))
        if embedding:
            metadata = {
                **doc_metadata,
                'file_hash': file.hash,
                'file_path': file.path,
                'chunk_index': idx,
                'total_chunks': total_chunks
            }
            repo.save_chunk(chunk, metadata, embedding)
            inserted_count += 1
    
    cache_hits = total_chunks - len(uncached_chunks)
    logger.info(f"✅ Embedded {inserted_count}/{total_chunks} | cache_hits={cache_hits}")
    return inserted_count
```

## Тестирование

```python
from unittest.mock import MagicMock
from contracts import FileSnapshot
from embedders.your_embedder import your_embedder

# Мокаем репозиторий
repo = MagicMock()
repo.delete_chunks_by_hash.return_value = 0

file = FileSnapshot(hash="test123", path="/test.txt", raw_text="Test text")
chunks = ["Chunk 1", "Chunk 2", "Chunk 3"]

count = your_embedder(repo, file, chunks, {"extension": "txt"})
print(f"Saved {count} chunks")

# Проверяем вызовы
repo.delete_chunks_by_hash.assert_called_once_with("test123")
assert repo.save_chunk.call_count == 3
```

## Отладка

Если эмбеддер не работает:

1. Проверьте, что имя в `EMBEDDERS` совпадает с `EMBEDDER_BACKEND`
2. Проверьте импорт в `__init__.py`
3. Проверьте доступность API (Ollama, OpenAI и т.д.)
4. Проверьте логи: `docker logs alpaca-ingest-1 2>&1 | grep embedder`
5. Убедитесь, что `repo.save_chunk()` получает корректные данные
