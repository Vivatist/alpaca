# Как добавить новый Cleaner в ALPACA RAG

## Обзор

Cleaner — это компонент пайплайна, который **очищает/нормализует текст** между парсингом и чанкингом (или между чанкингом и эмбеддингом). 

Текущий пайплайн:
```
Parser → Chunker → Embedder
```

После добавления cleaner:
```
Parser → Cleaner → Chunker → Embedder
```

---

## Шаг 1: Создать доменный контракт (type alias)

Создайте файл `core/domain/document_processing/cleaners/__init__.py`:

```python
"""
Доменный тип для клинеров (Cleaner).

=== НАЗНАЧЕНИЕ ===
Определяет контракт для функций, очищающих распарсенный текст
документа перед разбиением на чанки.

=== СИГНАТУРА ===
    Cleaner = Callable[[FileSnapshot], str]

Принимает: FileSnapshot с заполненным raw_text
Возвращает: очищенный текст (строка)

=== ИСПОЛЬЗОВАНИЕ ===

    from core.domain.document_processing.cleaners import Cleaner
    from core.domain.files import FileSnapshot

    # Типизация клинера
    def my_cleaner(file: FileSnapshot) -> str:
        text = file.raw_text or ""
        # Удалить лишние пробелы
        text = " ".join(text.split())
        return text

    # Использовать в use-case
    cleaner: Cleaner = my_cleaner
    cleaned_text = cleaner(file)
"""

from __future__ import annotations

from typing import Callable

from core.domain.files.models import FileSnapshot

# Контракт: принимает FileSnapshot, возвращает очищенный текст
Cleaner = Callable[[FileSnapshot], str]

__all__ = ["Cleaner"]
```

---

## Шаг 2: Экспортировать контракт из домена

Обновите файл `core/domain/document_processing/__init__.py`:

```python
"""
Доменные типы и контракты для обработки документов.
"""

from .parsers import ParserProtocol
from .parsers.registry import ParserRegistry
from .chunkers import Chunker
from .cleaners import Cleaner   # <-- Добавить
from .embedders import Embedder

__all__ = [
    "ParserProtocol",
    "ParserRegistry", 
    "Chunker",
    "Cleaner",     # <-- Добавить
    "Embedder",
]
```

---

## Шаг 3: Создать реализацию cleaner

Создайте директорию и файл:
```
core/application/document_processing/cleaners/
├── __init__.py
└── text_cleaner.py
```

### `core/application/document_processing/cleaners/__init__.py`:

```python
"""Модуль очистки текста."""

from .text_cleaner import clean_text

__all__ = ["clean_text"]
```

### `core/application/document_processing/cleaners/text_cleaner.py`:

```python
"""Реализация текстового клинера."""
import re
from typing import Optional
from utils.logging import get_logger
from core.domain.files.models import FileSnapshot

logger = get_logger("core.cleaner")


def clean_text(file: FileSnapshot) -> str:
    """Очищает текст документа.
    
    Args:
        file: FileSnapshot с заполненным raw_text
        
    Returns:
        str: очищенный текст
    """
    text = file.raw_text or ""
    
    if not text:
        logger.warning(f"Empty text for {file.path}")
        return ""
    
    try:
        logger.info(f"🧹 Cleaning: {file.path}")
        
        original_len = len(text)
        
        # 1. Удаляем множественные пробелы
        text = re.sub(r' +', ' ', text)
        
        # 2. Удаляем множественные переносы строк (больше 2)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # 3. Удаляем пробелы в начале/конце строк
        text = '\n'.join(line.strip() for line in text.split('\n'))
        
        # 4. Удаляем управляющие символы (кроме \n и \t)
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
        
        # 5. Нормализуем Unicode пробелы
        text = re.sub(r'[\u00a0\u2000-\u200b\u202f\u205f\u3000]', ' ', text)
        
        # 6. Финальный strip
        text = text.strip()
        
        cleaned_len = len(text)
        reduction = ((original_len - cleaned_len) / original_len * 100) if original_len > 0 else 0
        
        logger.info(f"✅ Cleaned: {file.path} | {original_len} → {cleaned_len} chars ({reduction:.1f}% reduced)")
        
        return text
        
    except Exception as e:
        logger.error(f"❌ Cleaning failed | file={file.path} error={e}")
        return file.raw_text or ""  # Возвращаем оригинал при ошибке
```

---

## Шаг 4: Интегрировать в use-case IngestDocument

Обновите `core/application/processing/use_cases.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from threading import Semaphore
from typing import Dict, Any, Optional
import os

from utils.logging import get_logger
from core.domain.files.repository import FileRepository
from core.domain.files.models import FileSnapshot
from core.domain.document_processing import ParserRegistry, Chunker, Embedder, Cleaner  # <-- Добавить Cleaner


@dataclass
class IngestDocument:
    """Полный пайплайн обработки документа (parse → clean → chunk → embed)."""

    repository: FileRepository
    parser_registry: ParserRegistry
    chunker: Chunker
    embedder: Embedder
    parse_semaphore: Semaphore
    embed_semaphore: Semaphore
    cleaner: Optional[Cleaner] = None    # <-- Добавить (опционально)
    temp_dir: str = "/home/alpaca/tmp_md"
    logger_name: str = field(default="core.ingest")

    def __post_init__(self):
        self.logger = get_logger(self.logger_name)

    def __call__(self, file: FileSnapshot) -> bool:
        self.logger.info(f"🍎 Start ingest pipeline: {file.path}")
        try:
            # 1. Parse
            parser = self.parser_registry.get_parser(file.path)
            if parser is None:
                self.logger.error(f"Unsupported file type: {file.path}")
                self.repository.mark_as_error(file.hash)
                return False

            with self.parse_semaphore:
                file.raw_text = parser.parse(file)
                self.repository.set_raw_text(file.hash, file.raw_text)

            self.logger.info(f"✅ Parsed: {len(file.raw_text) if file.raw_text else 0} chars")

            # 2. Clean (если cleaner задан)         # <-- Новый шаг
            if self.cleaner is not None:
                file.raw_text = self.cleaner(file)
                self.logger.info(f"✅ Cleaned: {len(file.raw_text) if file.raw_text else 0} chars")

            # 3. Save to disk for debugging
            self._save_to_disk(file)

            # 4. Chunk
            chunks = self.chunker(file)
            if not chunks:
                self.logger.warning(f"No chunks created for {file.path}")
                self.repository.mark_as_error(file.hash)
                return False

            # 5. Embed
            with self.embed_semaphore:
                chunks_count = self.embedder(self.repository, file, chunks)

            # ... остальной код без изменений
```

---

## Шаг 5: Подключить в bootstrap

Обновите `core/application/bootstrap.py`:

```python
from core.application.document_processing.chunkers import chunk_document as default_chunker
from core.application.document_processing.cleaners import clean_text  # <-- Добавить
from core.application.document_processing.embedders import custom_embedding, langchain_embedding


def build_worker_application(app_settings: Settings = settings) -> WorkerApplication:
    """Собирает и возвращает готовый worker."""
    
    # ... существующий код ...
    
    # 3. Chunker
    chunker = default_chunker
    
    # 3.5 Cleaner (опционально)                    # <-- Добавить
    cleaner = clean_text if app_settings.ENABLE_CLEANER else None
    
    # 4. Embedder
    if app_settings.EMBEDDER_BACKEND == "langchain":
        embedder = langchain_embedding
    else:
        embedder = custom_embedding
    
    # 5. Ingest pipeline
    ingest = IngestDocument(
        repository=repository,
        parser_registry=parsers,
        chunker=chunker,
        cleaner=cleaner,           # <-- Добавить
        embedder=embedder,
        parse_semaphore=Semaphore(app_settings.WORKER_MAX_CONCURRENT_PARSING),
        embed_semaphore=Semaphore(app_settings.WORKER_MAX_CONCURRENT_EMBEDDING),
    )
    
    # ... остальной код ...
```

---

## Шаг 6: Добавить настройку в settings.py

```python
# settings.py

class Settings(BaseSettings):
    # ... существующие настройки ...
    
    # Cleaner
    ENABLE_CLEANER: bool = True  # Включить очистку текста
```

---

## Шаг 7: Написать тесты

Создайте `tests/unit/test_cleaner.py`:

```python
"""Тесты для text_cleaner."""
import pytest
from core.domain.files.models import FileSnapshot
from core.application.document_processing.cleaners import clean_text


@pytest.fixture
def file_snapshot():
    """Фикстура FileSnapshot."""
    return FileSnapshot(
        hash="abc123",
        path="test.docx",
        size=1000,
        mtime=1234567890.0,
        status_sync="added",
        raw_text=None,
    )


def test_clean_text_removes_extra_spaces(file_snapshot):
    """Проверяем удаление лишних пробелов."""
    file_snapshot.raw_text = "Hello    world   test"
    result = clean_text(file_snapshot)
    assert result == "Hello world test"


def test_clean_text_removes_extra_newlines(file_snapshot):
    """Проверяем нормализацию переносов."""
    file_snapshot.raw_text = "Line1\n\n\n\n\nLine2"
    result = clean_text(file_snapshot)
    assert result == "Line1\n\nLine2"


def test_clean_text_handles_empty(file_snapshot):
    """Проверяем обработку пустого текста."""
    file_snapshot.raw_text = ""
    result = clean_text(file_snapshot)
    assert result == ""


def test_clean_text_handles_none(file_snapshot):
    """Проверяем обработку None."""
    file_snapshot.raw_text = None
    result = clean_text(file_snapshot)
    assert result == ""


def test_clean_text_strips_lines(file_snapshot):
    """Проверяем удаление пробелов в начале/конце строк."""
    file_snapshot.raw_text = "  Line1  \n  Line2  "
    result = clean_text(file_snapshot)
    assert result == "Line1\nLine2"
```

Запуск тестов:
```bash
cd ~/alpaca && source venv/bin/activate
pytest tests/unit/test_cleaner.py -v
```

---

## Итоговая структура файлов

```
core/
├── domain/
│   └── document_processing/
│       ├── __init__.py          # Экспорт Cleaner
│       ├── cleaners/
│       │   └── __init__.py      # Cleaner type alias
│       ├── chunkers/
│       ├── embedders/
│       └── parsers/
│
├── application/
│   ├── bootstrap.py              # Подключение cleaner
│   ├── document_processing/
│   │   ├── cleaners/             # НОВАЯ ДИРЕКТОРИЯ
│   │   │   ├── __init__.py
│   │   │   └── text_cleaner.py
│   │   ├── chunkers/
│   │   ├── embedders/
│   │   └── parsers/
│   └── processing/
│       └── use_cases.py          # IngestDocument с cleaner
│
settings.py                       # ENABLE_CLEANER
tests/
└── unit/
    └── test_cleaner.py           # Тесты
```

---

## Альтернативные стратегии очистки

### Несколько cleaner'ов в цепочке

Если нужно несколько очисток, создайте композитный cleaner:

```python
# core/application/document_processing/cleaners/composite.py

from typing import List
from core.domain.document_processing.cleaners import Cleaner
from core.domain.files.models import FileSnapshot


def compose_cleaners(*cleaners: Cleaner) -> Cleaner:
    """Объединяет несколько клинеров в цепочку."""
    
    def composite(file: FileSnapshot) -> str:
        text = file.raw_text
        for cleaner in cleaners:
            file.raw_text = text
            text = cleaner(file)
        return text
    
    return composite


# Использование:
from .text_cleaner import clean_text
from .html_cleaner import clean_html

full_cleaner = compose_cleaners(clean_html, clean_text)
```

### Cleaner по типу файла

```python
# core/application/document_processing/cleaners/registry.py

from typing import Dict, Tuple, Optional
from core.domain.document_processing.cleaners import Cleaner


class CleanerRegistry:
    """Реестр клинеров по расширениям файлов."""
    
    def __init__(self, cleaners: Dict[Tuple[str, ...], Cleaner], default: Cleaner):
        self._cleaners = cleaners
        self._default = default
    
    def get_cleaner(self, file_path: str) -> Cleaner:
        lower_path = file_path.lower()
        for extensions, cleaner in self._cleaners.items():
            if lower_path.endswith(extensions):
                return cleaner
        return self._default
```

---

## Чек-лист

- [ ] Создать `core/domain/document_processing/cleaners/__init__.py` с type alias
- [ ] Добавить экспорт в `core/domain/document_processing/__init__.py`
- [ ] Создать `core/application/document_processing/cleaners/` с реализацией
- [ ] Обновить `IngestDocument` — добавить параметр `cleaner`
- [ ] Обновить `bootstrap.py` — подключить cleaner
- [ ] Добавить `ENABLE_CLEANER` в `settings.py`
- [ ] Написать unit-тесты
- [ ] Запустить `pytest tests/unit/test_cleaner.py -v`
- [ ] Проверить интеграцию: `python main.py`
