# Как добавить новый MetaExtractor

## Структура модуля metaextractors

```
metaextractors/
├── __init__.py       ← реестр + build_metaextractor()
├── simple.py         ← simple_extractor() - только расширение
├── llm.py            ← llm_extractor() - анализ через Ollama
└── your_extractor.py ← ваш новый экстрактор
```

## Шаги

### 1. Создайте файл с экстрактором

Создайте новый файл, например `regex.py`:

```python
"""
Описание: что извлекает этот экстрактор.
"""

import os
import re
from typing import Dict, Any

from logging_config import get_logger
from contracts import FileSnapshot

logger = get_logger("ingest.metaextractor.regex")


def regex_extractor(file: FileSnapshot) -> Dict[str, Any]:
    """
    Regex экстрактор: извлекает метаданные по паттернам.
    
    Args:
        file: FileSnapshot с заполненным raw_text
        
    Returns:
        Dict с метаданными
    """
    _, ext = os.path.splitext(file.path)
    ext = ext.lower().lstrip('.')
    
    metadata = {
        "extension": ext
    }
    
    text = file.raw_text or ""
    if not text.strip():
        return metadata
    
    # Ваша логика извлечения метаданных
    # ...
    
    logger.debug(f"Regex extraction | file={file.path}")
    return metadata
```

### 2. Зарегистрируйте экстрактор в `__init__.py`

Добавьте импорт и запись в словарь EXTRACTORS:

```python
# В начале файла добавьте импорт
from .regex import regex_extractor

# В словарь EXTRACTORS добавьте запись
EXTRACTORS: dict[str, MetaExtractor] = {
    "simple": simple_extractor,
    "llm": llm_extractor,
    "regex": regex_extractor,  # ← новый экстрактор
}
```

### 3. Используйте экстрактор

В `docker-compose.yml` установите переменные:

```yaml
environment:
  ENABLE_METAEXTRACTOR: "true"
  METAEXTRACTOR_BACKEND: "regex"
```

## Правила написания экстракторов

1. **Сигнатура**: `def extractor_name(file: FileSnapshot) -> Dict[str, Any]`
2. **Обязательное поле**: всегда возвращайте `extension`
3. **Пустой текст**: возвращайте минимум `{"extension": ext}`
4. **Не бросайте исключения**: обрабатывайте ошибки внутри
5. **Стандартные поля**: `title`, `summary`, `keywords`, `author`, `date`

## Стандартная структура метаданных

```python
{
    "extension": "docx",           # Обязательное
    "title": "Название документа", # Опциональное
    "summary": "Краткое описание", # Опциональное
    "keywords": ["тег1", "тег2"], # Опциональное
    "author": "Имя автора",        # Опциональное
    "date": "2024-01-01",          # Опциональное
    "custom_field": "value"        # Любые дополнительные поля
}
```

## Пример: экстрактор дат из текста

```python
# date_extractor.py
"""
Извлекает даты из текста документа.
"""

import os
import re
from typing import Dict, Any, List

from logging_config import get_logger
from contracts import FileSnapshot

logger = get_logger("ingest.metaextractor.date")


def date_extractor(file: FileSnapshot) -> Dict[str, Any]:
    """Извлекает даты из текста документа."""
    _, ext = os.path.splitext(file.path)
    ext = ext.lower().lstrip('.')
    
    metadata = {"extension": ext}
    
    text = file.raw_text or ""
    if not text.strip():
        return metadata
    
    # Паттерны дат
    patterns = [
        r'\d{2}\.\d{2}\.\d{4}',      # DD.MM.YYYY
        r'\d{4}-\d{2}-\d{2}',        # YYYY-MM-DD
        r'\d{2}/\d{2}/\d{4}',        # DD/MM/YYYY
    ]
    
    dates: List[str] = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        dates.extend(matches)
    
    if dates:
        # Уникальные даты
        metadata["dates_found"] = list(set(dates))[:10]
        # Первая найденная дата как основная
        metadata["date"] = dates[0]
    
    logger.debug(f"Date extraction | file={file.path} dates={len(dates)}")
    return metadata
```

## Пример: экстрактор из имени файла

```python
# filename_extractor.py
"""
Извлекает метаданные из имени файла.
"""

import os
import re
from typing import Dict, Any

from logging_config import get_logger
from contracts import FileSnapshot

logger = get_logger("ingest.metaextractor.filename")


def filename_extractor(file: FileSnapshot) -> Dict[str, Any]:
    """Извлекает метаданные из имени файла."""
    basename = os.path.basename(file.path)
    name, ext = os.path.splitext(basename)
    ext = ext.lower().lstrip('.')
    
    metadata = {
        "extension": ext,
        "original_filename": basename
    }
    
    # Пробуем извлечь дату из имени (например: Report_2024-01-15.docx)
    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', name)
    if date_match:
        metadata["date"] = date_match.group(1)
    
    # Пробуем извлечь номер версии (например: Contract_v2.docx)
    version_match = re.search(r'[vV](\d+)', name)
    if version_match:
        metadata["version"] = int(version_match.group(1))
    
    logger.debug(f"Filename extraction | file={file.path}")
    return metadata
```

## Тестирование

```python
from contracts import FileSnapshot
from metaextractors.date_extractor import date_extractor

file = FileSnapshot(
    hash="test",
    path="/test.txt",
    raw_text="Документ от 15.01.2024. Срок до 2024-12-31."
)

metadata = date_extractor(file)
print(metadata)
# {'extension': 'txt', 'dates_found': ['15.01.2024', '2024-12-31'], 'date': '15.01.2024'}
```

## Отладка

Если экстрактор не работает:

1. Проверьте, что `ENABLE_METAEXTRACTOR=true`
2. Проверьте, что имя в `EXTRACTORS` совпадает с `METAEXTRACTOR_BACKEND`
3. Проверьте импорт в `__init__.py`
4. Проверьте логи: `docker logs alpaca-ingest-1 2>&1 | grep metaextractor`
