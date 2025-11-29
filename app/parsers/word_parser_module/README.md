# Word Parser Module

Модульная архитектура парсера Word документов для ALPACA RAG системы.

## 📊 Метрики рефакторинга

**До рефакторинга:**
- `word_parser.py`: **737 строк** (монолитный файл)

**После рефакторинга:**
- `word_parser.py`: **203 строки** (-72%)
- Дополнительные модули: **612 строк** (распределено по 5 модулям)
- **Итого**: 815 строк (+11% за счёт документации)

**Результат**: Главный файл уменьшился в **3.6 раза**, логика распределена по специализированным модулям.

## 🏗️ Архитектура

```
word_parser_module/
├── __init__.py                  # Публичный API модуля (21 строка)
├── word_parser.py               # Главный класс WordParser (203 строки) ⭐
├── image_converter.py           # Конвертация WMF/EMF → PNG (157 строк)
├── ocr_processor.py             # OCR обработка изображений (185 строк)
├── metadata_extractor.py        # Извлечение метаданных (65 строк)
└── fallback_parser.py           # Альтернативный парсер (116 строк)

Дополнительно общий для всех парсеров `document_converter.py` вынесен в `app/parsers/`.
```

## 📦 Модули

### `word_parser.py` - Главный класс

**203 строки** (было 737)

Координирует работу всех модулей, реализует основной pipeline:

```python
from app.parsers.word_parser_module.word_parser import WordParser

parser = WordParser(enable_ocr=True, ocr_strategy="auto")
result = parser.parse(file_object)
```

**Методы:**
- `parse(file)` - основной метод парсинга
- `_parse_with_markitdown()` - парсинг через Markitdown
- `_fallback_parse_internal()` - внутренний вызов fallback парсера

### `document_converter.py` (общий модуль) - Конвертация форматов

**68 строк**

Расположен в `app/parsers/document_converter.py`. Используется и Word, и PowerPoint парсерами.

```python
from app.parsers.document_converter import convert_doc_to_docx

docx_path = convert_doc_to_docx("/path/to/file.doc")
```

**Функции:**
- `convert_doc_to_docx(doc_path)` → `Optional[str]`
- `convert_ppt_to_pptx(ppt_path)` → `Optional[str]`

### `image_converter.py` - Конвертация изображений

**157 строк**

Конвертирует WMF/EMF изображения в PNG для OCR.

```python
from app.parsers.word_parser_module.image_converter import (
    convert_wmf_to_png,
    extract_images_via_pdf,
    get_image_extension
)
```

**Функции:**
- `convert_wmf_to_png(wmf_path, image_idx, temp_dir)` → `Optional[str]`
- `extract_images_via_pdf(docx_path, image_idx, temp_dir)` → `Optional[str]`
- `get_image_extension(content_type)` → `str`

**Методы конвертации:**
1. **ImageMagick** - основной метод (команды `magick` или `convert`)
2. **PIL** - fallback для простых форматов
3. **PDF метод** - конвертация DOCX→PDF→PNG через LibreOffice + pdf2image

### `ocr_processor.py` - OCR обработка

**185 строк**

Извлекает изображения из DOCX и выполняет OCR через Unstructured.

```python
from app.parsers.word_parser_module.ocr_processor import (
    extract_images_from_docx,
    process_images_with_ocr
)

images = extract_images_from_docx("/path/to/file.docx")
ocr_texts = process_images_with_ocr(images, ocr_strategy="auto")
```

**Функции:**
- `extract_images_from_docx(file_path)` → `List[Dict]`
  - Возвращает список словарей: `{'index', 'path', 'size', 'type'}`
- `process_images_with_ocr(images, ocr_strategy)` → `List[str]`
  - Возвращает список OCR текстов в том же порядке

**OCR конфигурация:**
- Языки: русский + английский (`["rus", "eng"]`)
- Стратегии: `"auto"` (по умолчанию), `"hi_res"`, `"fast"`
- Библиотека: Unstructured + pytesseract

### `metadata_extractor.py` - Метаданные

**65 строк**

Извлекает специфичные для Word метаданные.

```python
from app.parsers.word_parser_module.metadata_extractor import extract_word_metadata

metadata = extract_word_metadata("/path/to/file.docx")
# {'author': '...', 'subject': '...', 'pages': 5, 'paragraphs': 42, 'tables': 3, 'images': 2}
```

**Функции:**
- `extract_word_metadata(file_path)` → `Dict`
  - `author` - автор документа
  - `subject` - тема документа
  - `pages` - приблизительное количество страниц (250 слов = 1 страница)
  - `paragraphs` - количество параграфов
  - `tables` - количество таблиц
  - `images` - количество изображений

### `fallback_parser.py` - Альтернативный парсер

**116 строк**

Резервный парсер через python-docx или olefile для старых форматов.

```python
from app.parsers.word_parser_module.fallback_parser import (
    fallback_parse,
    table_to_markdown
)

text = fallback_parse("/path/to/file.docx")
```

**Функции:**
- `fallback_parse(file_path)` → `str`
  - Для `.doc` - пытается olefile
  - Для `.docx` - использует python-docx напрямую
- `table_to_markdown(table)` → `str`
  - Конвертирует таблицу Word в Markdown формат

## 🔄 Pipeline обработки

```
┌─────────────────┐
│   .doc файл     │
└────────┬────────┘
         │ 1. document_converter.convert_doc_to_docx()
         ↓
┌─────────────────┐
│   .docx файл    │
└────────┬────────┘
         │ 2. metadata_extractor.extract_word_metadata()
         │ 3. word_parser._parse_with_markitdown()
         │
         ├─→ 4a. ocr_processor.extract_images_from_docx()
         │   └─→ image_converter.convert_wmf_to_png()
         │       └─→ image_converter.extract_images_via_pdf()
         │
         └─→ 4b. ocr_processor.process_images_with_ocr()
             └─→ Замена base64 изображений на OCR текст
         │
         │ fallback: fallback_parser.fallback_parse()
         ↓
┌─────────────────┐
│  Markdown текст │
└─────────────────┘
```

## 🧪 Тестирование

Все 4 теста проходят успешно после рефакторинга:

```bash
pytest tests/test_parser.py -v -k word
```

**Тесты:**
- ✅ `test_parse_docx_file` - парсинг обычного DOCX
- ✅ `test_parse_nonexistent_file` - обработка несуществующего файла
- ✅ `test_parse_empty_docx` - обработка пустого DOCX
- ✅ `test_parse_docx_with_multiple_paragraphs` - парсинг с несколькими параграфами

**Проверка OCR на реальном файле:**

```bash
python test_refactored_parser.py
# ✅ Парсинг завершён
# 📊 Длина результата: 968 символов
```

## 📝 Использование

### Базовое использование

```python
from app.parsers.word_parser_module.word_parser import WordParser

# Создаем парсер
parser = WordParser(enable_ocr=True, ocr_strategy="auto")

# Парсим файл
result = parser.parse(file_object)
```

### Использование отдельных модулей

```python
# Конвертация .doc → .docx
from app.parsers.document_converter import convert_doc_to_docx
docx_path = convert_doc_to_docx("/path/to/file.doc")

# Извлечение изображений и OCR
from app.parsers.word_parser_module.ocr_processor import (
    extract_images_from_docx,
    process_images_with_ocr
)
images = extract_images_from_docx("/path/to/file.docx")
ocr_texts = process_images_with_ocr(images, ocr_strategy="hi_res")

# Извлечение метаданных
from app.parsers.word_parser_module.metadata_extractor import extract_word_metadata
metadata = extract_word_metadata("/path/to/file.docx")

# Fallback парсинг
from app.parsers.word_parser_module.fallback_parser import fallback_parse
text = fallback_parse("/path/to/file.docx")
```

## 🎯 Преимущества декомпозиции

1. **Читаемость** - главный файл уменьшился в 3.6 раза
2. **Повторное использование** - модули можно использовать независимо
3. **Тестирование** - легче писать unit-тесты для отдельных функций
4. **Поддержка** - изменения изолированы в конкретных модулях
5. **Документация** - каждый модуль документирован отдельно

## 🔒 Обратная совместимость

Публичный API остался без изменений:

```python
# До рефакторинга
from app.parsers.word_parser_module.word_parser import WordParser
parser = WordParser()

# После рефакторинга (тот же API)
from app.parsers.word_parser_module.word_parser import WordParser
parser = WordParser()
```

## 📋 Зависимости

- **markitdown** - основной парсер
- **python-docx** - работа с DOCX
- **unstructured** - OCR обработка
- **unstructured-pytesseract** - OCR движок
- **PIL/Pillow** - работа с изображениями
- **pdf2image** - конвертация PDF→PNG
- **LibreOffice** - конвертация DOC→DOCX и DOCX→PDF

## 🔧 Настройки

```python
# OCR включен (по умолчанию)
parser = WordParser(enable_ocr=True, ocr_strategy="auto")

# OCR выключен
parser = WordParser(enable_ocr=False)

# Высокое разрешение OCR
parser = WordParser(enable_ocr=True, ocr_strategy="hi_res")

# Быстрый OCR
parser = WordParser(enable_ocr=True, ocr_strategy="fast")
```

## 📌 История изменений

**v2.0** (Текущая версия)
- ✅ Декомпозиция на 6 модулей
- ✅ Главный файл: 737 → 203 строки (-72%)
- ✅ Все тесты проходят
- ✅ OCR работает корректно
- ✅ Обратная совместимость сохранена

**v1.0** (Оригинальная версия)
- Монолитный файл 737 строк
- Все функции в одном классе
