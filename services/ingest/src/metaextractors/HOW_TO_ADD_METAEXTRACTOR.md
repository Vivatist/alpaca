# Как добавить новый MetaExtractor

## Обзор

MetaExtractors извлекают метаданные из документов. Работают **последовательно** — каждый экстрактор получает накопленные метаданные от предыдущих и добавляет свои.

## Структура модуля

```
metaextractors/
├── __init__.py       ← реестр + get_extractor_pipeline() + build_metaextractor()
├── base.py           ← base_extractor() - расширение + дата модификации
├── llm.py            ← llm_extractor() - title, summary, keywords, entities, category
├── simple.py         ← simple_extractor() - deprecated, используйте base
└── your_extractor.py ← ваш новый экстрактор
```

## Стандартные метаданные

```python
{
    # base_extractor
    "extension": "docx",                    # Расширение файла
    "modified_at": "2025-12-04T15:30:00",   # Дата модификации ISO
    
    # llm_extractor
    "title": "Договор подряда №123",        # Заголовок документа
    "summary": "Договор на выполнение...",  # Краткое описание
    "keywords": ["договор", "подряд"],      # До 5 ключевых слов
    "entities": [                           # До 5 сущностей
        {"type": "person", "name": "Иванов И.И.", "role": "Директор"},
        {"type": "company", "name": "ООО Рога и Копыта", "role": "Заказчик"}
    ],
    "category": "Договор подряда",          # Категория документа
}
```

### Категории документов

1. Договор подряда
2. Договор купли-продажи
3. Трудовой договор
4. Протокол, меморандум
5. Доверенность
6. Акт выполненных работ
7. Счет-фактура, счет
8. Техническая документация
9. Презентация
10. Письмо
11. Бухгалтерская документация
12. Инструкция, регламент
13. Статья, публикация, книга
14. Прочее

## Шаги для добавления экстрактора

### 1. Создайте файл экстрактора

Создайте `metaextractors/my_extractor.py`:

```python
"""
Описание: что извлекает этот экстрактор.
"""

from typing import Dict, Any

from logging_config import get_logger
from contracts import FileSnapshot

logger = get_logger("ingest.metaextractor.my_extractor")


def my_extractor(file: FileSnapshot, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Мой экстрактор: извлекает XYZ.
    
    Args:
        file: FileSnapshot с информацией о файле и raw_text
        metadata: Накопленные метаданные от предыдущих экстракторов
        
    Returns:
        Dict с обновлёнными метаданными
    """
    result = metadata.copy()  # Копируем входящие метаданные
    
    text = file.raw_text or ""
    if not text.strip():
        return result  # Возвращаем без изменений
    
    # Ваша логика извлечения
    result["my_field"] = "extracted_value"
    
    logger.debug(f"My extraction | file={file.path}")
    return result
```

### 2. Зарегистрируйте в `__init__.py`

```python
from .my_extractor import my_extractor

EXTRACTORS: Dict[str, ExtractorFunc] = {
    "base": base_extractor,
    "llm": llm_extractor,
    "my_extractor": my_extractor,  # ← добавьте сюда
}
```

### 3. Настройте pipeline в docker-compose.yml

```yaml
environment:
  - ENABLE_METAEXTRACTOR=true
  - METAEXTRACTOR_PIPELINE=["base","my_extractor","llm"]
```

Pipeline выполняется слева направо: base → my_extractor → llm

## Правила

1. **Сигнатура**: `def extractor(file: FileSnapshot, metadata: Dict[str, Any]) -> Dict[str, Any]`
2. **Копируйте metadata**: `result = metadata.copy()` в начале
3. **Не бросайте исключения**: обрабатывайте ошибки внутри, возвращайте metadata без изменений
4. **Логируйте**: используйте `get_logger()` для отладки

## Примеры экстракторов для реализации

### regex_extractor
Извлечение по regex-паттернам:
- Номера договоров
- ИНН/ОГРН
- Даты в тексте
- Email/телефоны

### ocr_metadata_extractor
Для отсканированных документов:
- Качество OCR
- Язык документа
- Наличие рукописного текста

### structure_extractor
Анализ структуры:
- Количество страниц
- Наличие таблиц
- Наличие изображений
