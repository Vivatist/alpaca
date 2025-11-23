# ALPACA Document Parsers

Набор парсеров для конвертации документов в Markdown с метаданными для RAG системы.

## 📦 Структура

```
parsers/
├── base_parser.py          # Базовый класс для всех парсеров
├── markdown_writer.py      # Централизованный модуль сохранения
├── COMPARISON.md           # Подробное сравнение Word vs PDF vs TXT
├── MARKDOWN_WRITER.md      # Документация MarkdownWriter
├── word/
│   ├── word_parser.py      # Word парсер (.doc/.docx)
│   ├── PROCESS_FLOW.md     # Схема процесса Word
│   └── README.md           # Документация Word парсера
├── pdf/
│   ├── pdf_parser.py       # PDF парсер
│   ├── PROCESS_FLOW.md     # Схема процесса PDF
│   └── README.md           # Документация PDF парсера
├── txt/
│   ├── txt_parser.py       # TXT парсер с определением кодировки
│   ├── PROCESS_FLOW.md     # Схема процесса TXT
│   └── README.md           # Документация TXT парсера
└── mock/
    └── mock_parser.py      # Тестовый парсер для разработки
```

## 🎯 Быстрый старт

### Word документы

```python
from parsers.word.word_parser import WordParser

# Инициализация с OCR
parser = WordParser(enable_ocr=True, ocr_strategy='auto')

# Парсинг
result = parser.parse('/path/to/document.docx')

if result['success']:
    # Сохранение в Markdown
    parser.save_to_markdown_file(result, '/output/document.md')
    
    print(f"Метаданные: {result['metadata']}")
    print(f"Изображений: {len(result['images'])}")
```

### TXT документы

```python
from parsers.txt.txt_parser import TXTParser

# Инициализация
parser = TXTParser()

# Парсинг с автоопределением кодировки
result = parser.parse('/path/to/document.txt')

if result['status'] == 'success':
    print(f"Метаданные: {result['metadata']}")
    print(f"Кодировка: {result['metadata']['encoding']}")
    print(f"Строк: {result['metadata']['lines']}")
```

### PDF документы

```python
from parsers.pdf.pdf_parser import PDFParser

# Инициализация с OCR
parser = PDFParser(enable_ocr=True, ocr_strategy='auto')

# Парсинг
result = parser.parse('/path/to/document.pdf')

if result['success']:
    # Сохранение в Markdown
    parser.save_to_markdown_file(result, '/output/document.md')
    
    print(f"Метаданные: {result['metadata']}")
    print(f"Страниц: {result['metadata']['pages']}")
```

## 📊 Сравнение парсеров

| Характеристика | Word | PDF | TXT |
|---------------|------|-----|-----|
| **Форматы** | .doc, .docx | .pdf | .txt, .log, .eml |
| **Этапов обработки** | 7 | 5 | **3** |
| **OCR** | По изображениям | Весь документ | ❌ |
| **Автоопределение OCR** | ❌ | ✅ | N/A |
| **Определение кодировки** | N/A | N/A | **✅ chardet** |
| **Скорость (текст)** | ~0.5-1s | ~0.5-2s | **~10-15ms** |
| **Скорость (OCR)** | 2-5s/изображение | 3-10s/страница | N/A |
| **Постраничность** | ❌ | ✅ | ❌ |
| **Лучший выбор для** | Контракты, структура | Сканы, изображения | **Legacy, логи, скорость** |

**Подробности**: См. [COMPARISON.md](./COMPARISON.md)

## 🔑 Общие возможности

### 1. Извлечение текста
- Сохранение структуры (заголовки, списки, таблицы)
- Поддержка русского и английского языков
- Конвертация в Markdown формат

### 2. OCR (опционально)
- **Word**: OCR встроенных изображений
- **PDF**: OCR отсканированных страниц или всего документа
- Библиотека: Unstructured + Tesseract
- Языки: `rus`, `eng`

### 3. Метаданные
- Автор, дата создания/модификации
- Количество страниц/параграфов
- Информация о структуре документа
- Формат: YAML header для RAG

### 4. YAML Header
```yaml
---
document_type: pdf|word|txt
file_name: Договор_123.pdf
parser: alpaca-{type}-parser
title: "Договор поставки"
author: "ООО Георезонанс"
pages: 25
encoding: windows-1251    # TXT only
lines: 150                # TXT only
ocr_enabled: true         # PDF/Word only
---
```

## ⚙️ Конфигурация OCR

### Стратегии OCR

| Стратегия | Описание | Скорость | Точность | Использование |
|-----------|----------|----------|----------|--------------|
| `auto` | Автоматический выбор | ⚡⚡ Средняя | ✅✅ Высокая | **Production (рекомендуется)** |
| `fast` | Минимальный OCR | ⚡⚡⚡ Высокая | ✅ Низкая | Тестирование, массовая обработка |
| `hi_res` | Максимальное качество | ⚡ Низкая | ✅✅✅ Максимальная | Важные документы |
| `ocr_only` | Только OCR | ⚡ Низкая | ✅✅ Высокая | Чистые сканы (PDF) |

### Примеры конфигурации

```python
# Без OCR (только текст)
parser = PDFParser(enable_ocr=False)

# Балансированный режим (production)
parser = PDFParser(enable_ocr=True, ocr_strategy='auto')

# Максимальное качество
parser = PDFParser(enable_ocr=True, ocr_strategy='hi_res')
```

## 🏗️ Базовый класс (BaseParser)

Все парсеры наследуются от `BaseParser`:

```python
from parsers.base_parser import BaseParser

class CustomParser(BaseParser):
    def __init__(self):
        super().__init__("custom-parser")
    
    def parse(self, file_path: str) -> Dict:
        """Обязательный метод для реализации"""
        return {
            'markdown': '...',
            'metadata': {...},
            'yaml_header': '...',
            'success': True,
            'error': None
        }
```

### Общие методы

- `save_to_markdown_file(parse_result, output_path)` - сохранение результата
- `_generate_yaml_header(metadata, file_path, doc_type)` - генерация YAML
- `logger` - централизованный логгер (alpaca_logger)

## 🚀 Интеграция с Celery

Парсеры используются в Celery задачах:

```python
# txt_tasks.py
from parsers.txt.txt_parser import TXTParser
from parsers.markdown_writer import get_markdown_writer

txt_parser = TXTParser()
markdown_writer = get_markdown_writer('/volume_md')

@app.task(bind=True)
def process_txt_file(self, file_path: str, message: Dict) -> Dict:
    # Парсинг с определением кодировки
    parse_result = txt_parser.parse(file_path)
    
    # Сохранение через MarkdownWriter
    save_result = markdown_writer.save(
        parse_result=parse_result,
        file_name=file_name,
        timestamp=timestamp
    )
    return save_result
```

```python
# word_tasks.py
from parsers.word.word_parser import WordParser

word_parser = WordParser(enable_ocr=True, ocr_strategy='auto')

@app.task(bind=True)
def process_word_file(self, file_path: str, message: Dict) -> Dict:
    result = word_parser.parse(file_path)
    # ... обработка и сохранение
    return result
```

```python
# pdf_tasks.py
from parsers.pdf.pdf_parser import PDFParser
from parsers.markdown_writer import get_markdown_writer

pdf_parser = PDFParser(enable_ocr=True, ocr_strategy='auto')
markdown_writer = get_markdown_writer('/volume_md')

@app.task(bind=True)
def process_pdf_file(self, file_path: str, message: Dict) -> Dict:
    parse_result = pdf_parser.parse(file_path)
    save_result = markdown_writer.save(
        parse_result=parse_result,
        file_name=file_name,
        timestamp=timestamp
    )
    return save_result
```

**Все парсеры используют единый MarkdownWriter** для консистентности. См. [MARKDOWN_WRITER.md](./MARKDOWN_WRITER.md)

## 📚 Документация

### Детальная документация парсеров
- [TXT Parser README](./txt/README.md) - полное руководство (САМЫЙ БЫСТРЫЙ)
- [TXT Process Flow](./txt/PROCESS_FLOW.md) - схема 3-stage процесса
- [Word Parser README](./word/README.md) - полное руководство
- [Word Process Flow](./word/PROCESS_FLOW.md) - схема процесса
- [PDF Parser README](./pdf/README.md) - полное руководство
- [PDF Process Flow](./pdf/PROCESS_FLOW.md) - схема процесса

### Централизованный модуль сохранения
- [MARKDOWN_WRITER.md](./MARKDOWN_WRITER.md) - документация MarkdownWriter

### Сравнение и выбор
- [COMPARISON.md](./COMPARISON.md) - подробное сравнение Word vs PDF vs TXT

## 🧪 Mock Parser (для тестирования)

Используется для разработки и тестирования без реальной обработки:

```python
from parsers.mock.mock_parser import MockParser

# Автоматически используется если в конфиге:
# document_processors.mock_parsers.enabled: true

mock_parser = MockParser()
result = mock_parser.parse('/path/to/file.pdf')
# Возвращает заглушку без реальной обработки
```

## 🛠️ Зависимости

### Python библиотеки

```bash
# Общие
markitdown[all]>=0.0.1a2      # Word парсер
unstructured>=0.10.0          # OCR движок
pytesseract>=0.3.10           # Tesseract wrapper
pillow>=10.0.0                # Обработка изображений

# Word специфичные
python-docx==0.8.11           # Word документы

# PDF специфичные
pypdf>=3.17.0                 # PDF обработка
pdf2image>=1.16.0             # PDF → изображения

# TXT специфичные
chardet==5.2.0                # Определение кодировки (UTF-8, Windows-1251, CP866)
```

### Системные зависимости (Docker)

```dockerfile
# OCR
tesseract-ocr
tesseract-ocr-rus             # Русский язык
tesseract-ocr-eng             # Английский язык

# Word парсер
libreoffice                   # Конвертация .doc → .docx
imagemagick                   # WMF/EMF → PNG

# PDF парсер
poppler-utils                 # pdf2image backend
```

## 🎓 Лучшие практики

### Выбор парсера

**TXT** когда:
- **Legacy текстовые файлы** (Windows-1251, CP866)
- **Высокая скорость критична** (10-15ms vs 500ms-155s)
- Логи, email экспорты, простые заметки
- Массовая индексация (1000+ файлов)

**Word** когда:
- Документ в формате .docx/.doc
- Важна структура (параграфы, таблицы)
- Мало изображений (< 10)

**PDF** когда:
- Документ в формате .pdf
- Отсканированный документ
- Нужна постраничная структура
- Гибридный документ (текст + сканы)

### Оптимизация производительности

```python
# Массовая обработка (скорость)
parser = PDFParser(enable_ocr=False)  # Или strategy='fast'

# Важные документы (качество)
parser = PDFParser(enable_ocr=True, ocr_strategy='hi_res')

# Production (баланс)
parser = PDFParser(enable_ocr=True, ocr_strategy='auto')
```

### Обработка ошибок

```python
result = parser.parse(file_path)

if not result['success']:
    logger.error(f"Parsing failed: {result['error']}")
    # Обработка ошибки
else:
    # Сохранение результата
    parser.save_to_markdown_file(result, output_path)
```

## 📈 Мониторинг

Все парсеры логируют ключевые события:

```python
logger.info(f"Parsing started | file={filename}")
logger.info(f"Metadata extracted | pages={metadata['pages']}")
logger.info(f"OCR processing | images={count} strategy={strategy}")
logger.info(f"Parsing complete | duration={time:.2f}s content_length={len(markdown)}")
```

Логи доступны в Grafana через Loki:
```
{service="document-processors"} |= "txt-parser"     # TXT парсер (самый быстрый)
{service="document-processors"} |= "word-parser"
{service="document-processors"} |= "pdf-parser"
```

## 🔧 Разработка

### Создание нового парсера

1. Создайте класс, наследующий `BaseParser`
2. Реализуйте метод `parse(file_path: str) -> Dict`
3. Используйте `self.logger` для логирования
4. Возвращайте стандартную структуру результата

```python
from parsers.base_parser import BaseParser

class ExcelParser(BaseParser):
    def __init__(self):
        super().__init__("excel-parser")
    
    def parse(self, file_path: str) -> Dict:
        self.logger.info(f"Parsing Excel | file={file_path}")
        
        # Ваша логика парсинга
        
        return {
            'markdown': '...',
            'metadata': {...},
            'yaml_header': self._generate_yaml_header(...),
            'success': True,
            'error': None
        }
```

### Тестирование

```python
# Локальное тестирование
python -c "
from parsers.pdf.pdf_parser import PDFParser
parser = PDFParser(enable_ocr=True)
result = parser.parse('test.pdf')
print(result['metadata'])
"

# В Docker контейнере
docker exec alpaca-document-processors python -c "..."
```

---

## 📞 Поддержка

Вопросы и проблемы:
- Проверьте [COMPARISON.md](./COMPARISON.md) для выбора парсера
- Изучите [PROCESS_FLOW.md](./word/PROCESS_FLOW.md) для понимания процесса
- Проверьте логи в Grafana: `{service="document-processors"}`

**Версия**: 1.0.0  
**Обновлено**: 28 октября 2025
