# Как добавить новый Chunker

## Структура модуля chunkers

```
chunkers/
├── __init__.py      ← реестр + build_chunker()
├── simple.py        ← simple_chunker()
├── smart.py         ← smart_chunker() с LangChain
└── your_chunker.py  ← ваш новый чанкер
```

## Шаги

### 1. Создайте файл с чанкером

Создайте новый файл, например `semantic.py`:

```python
"""
Описание: что делает этот чанкер.
"""

from typing import List

from logging_config import get_logger
from contracts import FileSnapshot
from settings import settings

logger = get_logger("ingest.chunker.semantic")


def semantic_chunker(file: FileSnapshot) -> List[str]:
    """
    Семантический чанкер: разбивает текст по смысловым блокам.
    
    Args:
        file: FileSnapshot с заполненным raw_text
        
    Returns:
        Список чанков
    """
    text = file.raw_text or ""
    
    if not text.strip():
        logger.warning(f"Empty text for chunking | file={file.path}")
        return []
    
    # Ваша логика разбиения
    chunks = []
    
    # ... реализация ...
    
    logger.info(f"Semantic chunking complete | file={file.path} chunks={len(chunks)}")
    return chunks
```

### 2. Зарегистрируйте чанкер в `__init__.py`

Добавьте импорт и запись в словарь CHUNKERS:

```python
# В начале файла добавьте импорт
from .semantic import semantic_chunker

# В словарь CHUNKERS добавьте запись
CHUNKERS: dict[str, Chunker] = {
    "simple": simple_chunker,
    "smart": smart_chunker,
    "semantic": semantic_chunker,  # ← новый чанкер
}
```

### 3. Используйте чанкер

В `docker-compose.yml` установите переменную `CHUNKER_BACKEND`:

```yaml
environment:
  CHUNKER_BACKEND: "semantic"
```

## Правила написания чанкеров

1. **Сигнатура**: `def chunker_name(file: FileSnapshot) -> List[str]`
2. **Входные данные**: текст в `file.raw_text`
3. **Настройки**: используйте `settings.CHUNK_SIZE` и `settings.CHUNK_OVERLAP`
4. **Пустой текст**: возвращайте пустой список `[]`
5. **Логирование**: логируйте количество чанков в конце
6. **Fallback**: при ошибках можно fallback на simple_chunker

## Доступные настройки

```python
settings.CHUNK_SIZE      # Максимальный размер чанка (символов)
settings.CHUNK_OVERLAP   # Перекрытие между чанками (символов)
```

## Пример: чанкер по предложениям

```python
# sentence.py
"""
Разбивает текст по предложениям, группируя до CHUNK_SIZE.
"""

import re
from typing import List

from logging_config import get_logger
from contracts import FileSnapshot
from settings import settings

logger = get_logger("ingest.chunker.sentence")


def sentence_chunker(file: FileSnapshot) -> List[str]:
    """Разбивает текст по предложениям."""
    text = file.raw_text or ""
    
    if not text.strip():
        return []
    
    # Разбиваем на предложения
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        
        if len(current_chunk) + len(sentence) + 1 <= settings.CHUNK_SIZE:
            if current_chunk:
                current_chunk += " " + sentence
            else:
                current_chunk = sentence
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = sentence
    
    if current_chunk:
        chunks.append(current_chunk)
    
    logger.info(f"Sentence chunking complete | file={file.path} chunks={len(chunks)}")
    return chunks
```

## Тестирование

```python
from contracts import FileSnapshot
from chunkers.sentence import sentence_chunker

file = FileSnapshot(
    hash="test",
    path="/test.txt",
    raw_text="Первое предложение. Второе предложение. Третье."
)

chunks = sentence_chunker(file)
for i, chunk in enumerate(chunks):
    print(f"Chunk {i}: {chunk[:50]}...")
```

## Отладка

Если чанкер не работает:

1. Проверьте, что имя в `CHUNKERS` совпадает с `CHUNKER_BACKEND`
2. Проверьте импорт в `__init__.py`
3. Убедитесь, что `file.raw_text` заполнен (парсинг прошёл успешно)
4. Проверьте логи: `docker logs alpaca-ingest-1 2>&1 | grep chunker`
