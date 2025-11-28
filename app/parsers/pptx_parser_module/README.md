# PPTX Parser для ALPACA

Парсер PowerPoint презентаций (.pptx) для RAG системы ALPACA.

## Возможности

- ✅ Парсинг текста из слайдов PowerPoint
- ✅ Поддержка русскоязычных и английских презентаций
- ✅ Извлечение метаданных (автор, название, количество слайдов)
- ✅ Парсинг таблиц с конвертацией в Markdown
- ✅ Генерация YAML header для RAG индексации
- ✅ Экспорт в Markdown формат
- ❌ БЕЗ OCR для изображений (только текстовый контент)

## Зависимости

### Основные библиотеки:
- **unstructured[pptx]** - основной парсер (с поддержкой русского языка)
- **python-pptx** - извлечение метаданных и fallback парсинг

### Установка:
```bash
pip install unstructured[pptx] python-pptx
```

Или через requirements.txt проекта:
```bash
pip install -r document-processors/requirements.txt
```

## Использование

### В коде:

```python
from parsers.pptx import PptxParser

# Инициализация парсера
parser = PptxParser()

# Парсинг файла
result = parser.parse("presentation.pptx", file_hash="abc123")

if result['success']:
    print(f"Slides: {result['metadata']['slides']}")
    print(f"Markdown:\n{result['markdown']}")
    
    # Сохранение в файл
    parser.save_to_markdown_file(result, "output.md")
else:
    print(f"Error: {result['error']}")
```

### Из командной строки:

```bash
# Базовый парсинг
python document-processors/src/parsers/pptx/pptx_parser.py presentation.pptx

# С сохранением в файл
python document-processors/src/parsers/pptx/pptx_parser.py presentation.pptx -o output.md
```

## Структура результата

```python
{
    'success': bool,           # Статус парсинга
    'error': str | None,       # Сообщение об ошибке
    'markdown': str,           # Текст в Markdown формате
    'metadata': {              # Метаданные презентации
        # Общие метаданные (от BaseParser)
        'file_name': str,
        'file_path': str,
        'file_hash': str,
        'file_size': int,
        'file_modified': str,
        'file_created': str,
        
        # Специфичные для PPTX
        'author': str,
        'title': str,
        'subject': str,
        'slides': int,
        'ocr_enabled': bool
    },
    'yaml_header': str         # YAML header для RAG
}
```

## Формат Markdown

Парсер генерирует структурированный Markdown:

```markdown
---
document_type: pptx
parsed_date: 2025-10-28T12:00:00Z
parser: alpaca-pptx-parser
file_name: presentation.pptx
author: John Doe
slides: 10
---

## Слайд 1

### Заголовок презентации

Текст на первом слайде

---

## Слайд 2

### Основные пункты

- Пункт 1
- Пункт 2
- Пункт 3

| Колонка 1 | Колонка 2 |
|---|---|
| Данные 1 | Данные 2 |

---

...
```

## Парсинг Pipeline

1. **Unstructured** (основной метод):
   - Извлечение текста с поддержкой русского и английского
   - Распознавание структуры слайдов
   - Парсинг таблиц

2. **python-pptx** (fallback + метаданные):
   - Извлечение метаданных презентации
   - Резервный парсер если Unstructured недоступен
   - Извлечение текста из shapes и таблиц

3. **BaseParser**:
   - Добавление общих метаданных файла
   - Генерация YAML header
   - Сохранение в Markdown файл

## Ограничения

- ❌ Не извлекается текст из изображений (нет OCR)
- ❌ Не извлекаются SmartArt диаграммы (только текст)
- ❌ Сложные макеты могут терять форматирование
- ⚠️ Старый формат .ppt НЕ поддерживается (только .pptx)

## Тестирование

```bash
# Базовые тесты
python tests/test_pptx_parser.py

# Тест с реальным файлом
python tests/test_pptx_parser.py --file sample.pptx
```

## Логирование

Парсер использует централизованный `alpaca_logger` с plain text форматом:

```
2025-10-28 12:00:00 [INFO] pptx-parser: Parsing PowerPoint presentation | file=sample.pptx
2025-10-28 12:00:01 [INFO] pptx-parser: PowerPoint presentation parsed successfully | file=sample.pptx slides=10
```

## Интеграция с RAG

YAML header содержит все необходимые метаданные для индексации в Dify:

- `document_type`: 'pptx'
- `file_name`: имя файла
- `file_path`: полный путь
- `file_hash`: хэш от file-watcher
- `author`: автор презентации
- `slides`: количество слайдов
- `parsed_date`: дата парсинга

Эти метаданные позволяют RAG системе:
- Фильтровать документы по типу
- Отслеживать источник информации
- Предоставлять ссылки на оригинальные слайды
- Обновлять индекс при изменении файлов
