# PPTX Parser - Краткое руководство

## Что делает парсер

Парсер извлекает **текстовый контент** из PowerPoint презентаций (.pptx) и конвертирует его в Markdown с метаданными для RAG системы.

### ✅ Поддерживается:
- Текст из слайдов (заголовки, абзацы, списки)
- Таблицы (конвертируются в Markdown таблицы)
- Русский и английский языки
- Метаданные презентации (автор, название, количество слайдов)

### ❌ НЕ поддерживается:
- OCR для изображений (только текст)
- SmartArt диаграммы (только текст внутри)
- Старый формат .ppt (только .pptx)

## Быстрый старт

### 1. Установка зависимостей (локально):

```bash
pip install python-pptx>=0.6.21
pip install "unstructured[pptx]"
```

### 2. Использование в коде:

```python
from parsers.pptx import PptxParser

parser = PptxParser()
result = parser.parse("presentation.pptx")

if result['success']:
    print(f"Slides: {result['metadata']['slides']}")
    print(result['markdown'][:500])  # Первые 500 символов
```

### 3. Тестирование:

```bash
# Базовые тесты
python tests/test_pptx_parser.py

# Тест с вашим файлом
python tests/test_pptx_parser.py --file myfile.pptx
```

## Пример результата

**Входной файл:** `presentation.pptx` (5 слайдов, русский текст)

**Выходной Markdown:**

```markdown
---
document_type: pptx
parsed_date: 2025-10-28T12:00:00Z
parser: alpaca-pptx-parser
file_name: presentation.pptx
file_path: /path/to/presentation.pptx
file_hash: 1730123456-204800
file_size: 204800
author: Иван Иванов
title: Отчет по проекту
slides: 5
ocr_enabled: false
---

## Слайд 1

### Отчет по проекту ALPACA

Система управления документами для ООО "Георезонанс"

---

## Слайд 2

### Основные возможности

- Интеллектуальный поиск
- RAG технология
- Локальный LLM

...
```

## Интеграция с file-watcher

Парсер автоматически используется file-watcher для обработки `.pptx` файлов:

```python
# В file-watcher
from parsers.pptx import PptxParser

parser = PptxParser()
result = parser.parse(file_path, file_hash=watcher_hash)

# Отправка в Dify
send_to_dify(result['yaml_header'] + result['markdown'])
```

## Архитектура

```
.pptx файл
    ↓
[Unstructured] - основной парсер (с русским языком)
    ↓
[python-pptx] - метаданные + fallback
    ↓
[BaseParser] - общие метаданные + YAML header
    ↓
Markdown + YAML → Dify RAG
```

## Логирование

Парсер использует `alpaca_logger` с plain text форматом:

```
2025-10-28 12:00:00 [INFO] pptx-parser: Parsing PowerPoint presentation | file=test.pptx
2025-10-28 12:00:01 [INFO] pptx-parser: PowerPoint presentation parsed successfully | file=test.pptx slides=10
```

Логи доступны в Grafana через Loki: `{service="pptx-parser"}`

## Troubleshooting

### "Missing dependencies: unstructured[pptx]"

```bash
pip install "unstructured[pptx]"
```

Парсер будет работать с fallback на python-pptx, но качество хуже.

### "No module named 'pptx'"

```bash
pip install python-pptx>=0.6.21
```

### Плохое качество парсинга таблиц

Убедитесь что установлен unstructured - он лучше обрабатывает структуру:

```bash
pip install "unstructured[pptx]"
```

### Не распознается русский текст

Проверьте что unstructured установлен с поддержкой языков:

```python
from unstructured.partition.pptx import partition_pptx

elements = partition_pptx(
    filename="file.pptx",
    languages=["rus", "eng"]  # Русский + английский
)
```

## Дополнительная документация

- **README.md** - полная документация
- **INSTALL.md** - детальная установка
- **tests/test_pptx_parser.py** - примеры использования
