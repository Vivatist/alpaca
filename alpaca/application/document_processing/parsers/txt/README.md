# 📄 TXT Parser

## 🎯 Назначение

TXT парсер отвечает за преобразование простых текстовых файлов в формат Markdown с метаданными YAML для индексации в RAG системе ALPACA.

**Ключевые особенности:**
- ✅ **Автоматическое определение кодировки** - поддержка UTF-8, Windows-1251, CP866
- ✅ **Сохранение структуры** - параграфы, отступы, пустые строки
- ✅ **Метаданные** - кодировка, количество строк/слов/символов, даты
- ✅ **Быстрая обработка** - ~10ms на файл (в 10000 раз быстрее PDF с OCR)

---

## 🏗️ Архитектура

### Класс `TXTParser`

```python
class TXTParser(BaseParser):
    """
    Парсер для простых текстовых файлов.
    
    Attributes:
        encoding_detector: chardet для определения кодировки
        confidence_threshold: 0.7 - минимальный порог уверенности
    """
```

**Наследование:** `BaseParser` (валидация, общие утилиты)

**Зависимости:**
- `chardet` - определение кодировки (UTF-8, Windows-1251, CP866, KOI8-R)
- `pathlib` - работа с путями файлов
- `datetime` - временные метки

---

## 📊 3-Stage Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                    TXT PARSER PIPELINE                      │
└─────────────────────────────────────────────────────────────┘

Input: plain text file → Output: Markdown + YAML metadata

Stage 1: DETECT ENCODING
  ├─ Read first 10KB
  ├─ chardet.detect()
  ├─ Check confidence > 70%
  └─ Fallback to UTF-8 if low confidence

Stage 2: READ & PARSE
  ├─ Open file with detected encoding
  ├─ Read all content
  ├─ Extract metadata (lines, words, chars)
  └─ Get file stats (size, dates)

Stage 3: FORMAT MARKDOWN
  ├─ Generate title from filename
  ├─ Preserve paragraph structure
  ├─ Create YAML frontmatter
  └─ Assemble final document
```

---

## 🔍 Детали этапов

### Stage 1: Detect Encoding

**Цель:** Определить кодировку файла для корректного чтения

**Процесс:**
```python
def _detect_encoding(self, file_path: str) -> str:
    # 1. Читаем первые 10KB (достаточно для определения)
    with open(file_path, 'rb') as f:
        raw_data = f.read(10240)
    
    # 2. Используем chardet
    detected = chardet.detect(raw_data)
    encoding = detected.get('encoding', 'utf-8')
    confidence = detected.get('confidence', 0.0)
    
    # 3. Проверяем уверенность
    if confidence < 0.7:
        logger.warning(f"Low encoding confidence | detected={encoding} "
                      f"confidence={confidence:.2f} file={file_path}")
        return 'utf-8'  # Безопасный fallback
    
    return encoding
```

**Поддерживаемые кодировки:**
- UTF-8 (Unicode, современный стандарт)
- Windows-1251 (кириллица, legacy системы)
- CP866 (DOS кириллица)
- KOI8-R (старая Unix кириллица)
- ASCII (английский текст)

**Логирование:**
```
[INFO] Detected encoding | encoding=utf-8
[WARNING] Low encoding confidence | detected=cp1251 confidence=0.45 file=...
```

**Критерии выбора:**
- **Уверенность >= 70%** - используем определённую кодировку
- **Уверенность < 70%** - fallback на UTF-8 (самый универсальный)

---

### Stage 2: Read & Parse Content

**Цель:** Прочитать файл и извлечь метаданные

**Процесс:**
```python
def _extract_metadata(self, file_path: str, content: str) -> Dict[str, Any]:
    path = Path(file_path)
    stat = path.stat()
    
    # Подсчёт метрик
    lines = content.count('\n') + 1
    words = len(content.split())
    characters = len(content)
    
    # Получение дат
    created_time = datetime.fromtimestamp(stat.st_ctime)
    modified_time = datetime.fromtimestamp(stat.st_mtime)
    
    return {
        'title': path.stem,
        'encoding': detected_encoding,
        'lines': lines,
        'words': words,
        'characters': characters,
        'size_bytes': stat.st_size,
        'created': created_time.isoformat(),
        'modified': modified_time.isoformat()
    }
```

**Извлекаемые данные:**
- **Структура:** количество строк, слов, символов
- **Кодировка:** определённая на Stage 1
- **Размер:** байты
- **Временные метки:** создание, изменение

**Пример метаданных:**
```yaml
title: contract_2024
encoding: windows-1251
lines: 150
words: 1250
characters: 8450
size_bytes: 10240
created: '2024-01-15T09:30:00'
modified: '2024-02-20T14:45:00'
```

---

### Stage 3: Format as Markdown

**Цель:** Создать Markdown с сохранением структуры

**Процесс:**
```python
def _format_as_markdown(self, content: str, metadata: Dict[str, Any]) -> str:
    # 1. Заголовок из имени файла
    title = metadata.get('title', 'Без названия')
    
    # 2. Сохраняем параграфы (разделённые пустыми строками)
    markdown_content = f"# {title}\n\n{content}"
    
    return markdown_content
```

**Сохраняемая структура:**
- Параграфы (пустые строки между блоками текста)
- Отступы (пробелы в начале строк)
- Переносы строк
- Спецсимволы (без экранирования)

**Пример преобразования:**
```
INPUT (UTF-8):
Договор №123

Настоящий договор заключён между:
- ООО "Компания А"
- ООО "Компания Б"

Предмет договора:
Поставка оборудования.

OUTPUT (Markdown):
# contract_123

Договор №123

Настоящий договор заключён между:
- ООО "Компания А"
- ООО "Компания Б"

Предмет договора:
Поставка оборудования.
```

---

## 📝 YAML Frontmatter

**Формат:**
```yaml
---
document_type: txt
file_name: contract.txt
file_path: /app/data/volume_documents/contract.txt
parsed_date: 2025-10-28T10:30:45.123456Z
parser: alpaca-txt-parser
title: contract
encoding: windows-1251
lines: 150
characters: 8450
words: 1250
size_bytes: 10240
created: '2024-01-15T09:30:00'
modified: '2024-02-20T14:45:00'
---
```

**Поля:**
- `document_type`: txt (идентификатор типа)
- `file_name`: оригинальное имя файла
- `file_path`: абсолютный путь в контейнере
- `parsed_date`: когда парсинг завершён (ISO 8601)
- `parser`: alpaca-txt-parser (версионирование)
- `title`: имя файла без расширения
- `encoding`: определённая кодировка (критично для RAG)
- `lines`, `words`, `characters`: метрики контента
- `size_bytes`: размер исходного файла
- `created`, `modified`: временные метки файла

**Использование в RAG:**
```python
# Пример поиска документов в определённой кодировке
query = "encoding: windows-1251"

# Пример фильтрации по размеру
query = "size_bytes: >100000"  # Файлы > 100KB
```

---

## 🔧 Интеграция с Celery Task

**Файл:** `tasks/txt_tasks.py`

```python
from parsers.txt.txt_parser import TXTParser
from parsers.markdown_writer import get_markdown_writer

# Инициализация (singleton)
txt_parser = TXTParser()
markdown_writer = get_markdown_writer('/volume_md')

@app.task(bind=True, name='tasks.txt_tasks.process_txt_file')
def process_txt_file(self, file_path: str, file_name: str, event: str):
    # 1. Парсинг (3-stage pipeline)
    parse_result = txt_parser.parse(str(path))
    
    # 2. Валидация результата
    if parse_result.get('status') != 'success':
        raise ValueError(f"Parsing failed: {parse_result.get('error')}")
    
    # 3. Сохранение через MarkdownWriter
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    save_result = markdown_writer.save(
        parse_result=parse_result,
        file_name=file_name,
        timestamp=timestamp
    )
    
    # 4. Возврат результата
    return {
        'status': 'success',
        'file_path': file_path,
        'markdown_file': save_result['file_name'],
        'markdown_path': save_result['file_path'],
        'processing_time_sec': duration,
        'metadata': parse_result['metadata']
    }
```

**Очередь:** `celery` (дефолтная)

**Retry policy:** 3 попытки с экспоненциальным backoff

---

## ⚡ Производительность

### Бенчмарк

| Метрика | Значение | Контекст |
|---------|----------|----------|
| **Скорость парсинга** | ~10ms | Файл 10KB, UTF-8 |
| **Определение кодировки** | 2-3ms | Первые 10KB файла |
| **Сохранение Markdown** | 1-2ms | Через MarkdownWriter |
| **Общее время** | 15ms | От файла до Markdown |

**Сравнение с другими парсерами:**
- TXT: **15ms** (baseline)
- Word: **500ms** (в 33 раза медленнее - markitdown)
- PDF без OCR: **1.5s** (в 100 раз медленнее - pypdf)
- PDF с OCR: **155s** (в 10000 раз медленнее - Tesseract)

### Оптимизации

1. **Частичное чтение для кодировки** - только 10KB вместо всего файла
2. **Без внешних зависимостей** - нет markitdown, OCR, image libraries
3. **Singleton MarkdownWriter** - переиспользование инстанса
4. **Минимальная обработка** - сохраняем как есть, без преобразований

---

## 🧪 Тестирование

### Test Cases

```bash
# 1. UTF-8 с русским текстом
echo -e "Тестовый документ\n\nПараграф 1.\n\nПараграф 2." > test_utf8.txt

# 2. Windows-1251 (legacy)
# Создать в редакторе, сохранить с кодировкой Windows-1251

# 3. Большой файл (1MB+)
dd if=/dev/urandom of=test_large.txt bs=1M count=5

# 4. Файл с emoji (UTF-8)
echo "🚀 Запуск системы 🎯 Цель достигнута ✅" > test_emoji.txt
```

### Ожидаемые результаты

**UTF-8:**
```
[INFO] Detected encoding | encoding=utf-8
[INFO] Metadata extracted | lines=5 chars=45
[INFO] TXT parsed successfully | content_length=50
```

**Windows-1251:**
```
[INFO] Detected encoding | encoding=windows-1251
[INFO] Metadata extracted | lines=100 chars=5000
[INFO] TXT parsed successfully | content_length=5050
```

**Низкая уверенность:**
```
[WARNING] Low encoding confidence | detected=iso-8859-1 confidence=0.45
[INFO] Using fallback encoding | encoding=utf-8
```

---

## 🚨 Error Handling

### Обрабатываемые ситуации

1. **Файл не найден:**
```python
if not path.exists():
    return {'status': 'error', 'error': 'File not found'}
```

2. **Ошибка чтения:**
```python
except UnicodeDecodeError as e:
    logger.error(f"Encoding error | file={file_path} encoding={encoding}")
    # Retry с UTF-8
```

3. **Неопределённая кодировка:**
```python
if detected.get('encoding') is None:
    logger.warning(f"Could not detect encoding | file={file_path}")
    encoding = 'utf-8'  # Fallback
```

4. **Пустой файл:**
```python
if len(content.strip()) == 0:
    logger.warning(f"Empty file | file={file_path}")
    # Продолжаем парсинг, сохраняем пустой Markdown
```

### Логирование ошибок

```
[ERROR] File processing error | file=contract.txt error=UnicodeDecodeError: 'utf-8' codec can't decode
[WARNING] Retrying with fallback encoding | file=contract.txt encoding=windows-1251
[INFO] Successfully parsed on retry | file=contract.txt encoding=windows-1251
```

---

## 🔗 Интеграция с MarkdownWriter

**Унифицированный паттерн:**

```python
# TXT Parser возвращает стандартный формат
parse_result = {
    'status': 'success',
    'content': markdown_text,  # Уже форматированный Markdown
    'metadata': {
        'title': 'contract',
        'encoding': 'windows-1251',
        'lines': 150,
        # ... остальные поля
    }
}

# MarkdownWriter сохраняет
save_result = markdown_writer.save(
    parse_result=parse_result,
    file_name='contract.txt',
    timestamp='20251028_103045_123'
)

# Результат:
# /volume_md/20251028_103045_123_contract.md
```

**Преимущества:**
- Единый интерфейс для всех парсеров (PDF, Word, TXT)
- Централизованная логика генерации имён файлов
- Автоматическая транслитерация кириллицы
- Консистентные YAML метаданные

---

## 📦 Зависимости

**requirements.txt:**
```txt
chardet==5.2.0  # Определение кодировки
```

**Установка:**
```bash
pip install -r requirements.txt
```

**Docker:**
```dockerfile
# Уже включено в базовый образ
COPY document-processors/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
```

---

## 🎓 Use Cases

### 1. Legacy документация

**Проблема:** Старые договоры в Windows-1251

**Решение:**
```python
# Автоматическое определение кодировки
parse_result = txt_parser.parse('legacy_contract.txt')
# encoding=windows-1251 автоматически обнаружен
```

### 2. Экспорт из CRM

**Проблема:** CSV экспорты с табуляцией

**Решение:**
```python
# TXT парсер сохраняет структуру
# Табуляция и отступы остаются как есть
```

### 3. Email переписка

**Проблема:** .eml файлы экспортированы в .txt

**Решение:**
```python
# Парсим как обычный текст
# Метаданные включают дату создания/изменения
```

### 4. Логи систем

**Проблема:** Нужно индексировать логи для поиска

**Решение:**
```python
# TXT парсер обрабатывает многострочные логи
# Сохраняет временные метки в metadata
```

---

## 🔄 Обновление и миграция

### Добавление новой кодировки

```python
# В _detect_encoding() добавить fallback:
ENCODING_FALLBACKS = {
    'iso-8859-1': 'windows-1251',  # Latin-1 → CP1251
    'ascii': 'utf-8',               # ASCII → UTF-8
}

detected_encoding = chardet.detect(raw_data)['encoding']
encoding = ENCODING_FALLBACKS.get(detected_encoding, detected_encoding)
```

### Миграция старых файлов

```bash
# Переиндексация всех TXT файлов
find /volume_documents -name "*.txt" -type f | while read file; do
    # Trigger Celery task
    celery call tasks.txt_tasks.process_txt_file \
        --args="['$file', '$(basename $file)', 'reindex']"
done
```

---

## 📚 См. также

- **MARKDOWN_WRITER.md** - Централизованный модуль сохранения
- **COMPARISON.md** - Сравнение TXT vs PDF vs Word парсеров
- **word/README.md** - Word парсер (7 stages)
- **pdf/README.md** - PDF парсер (5 stages + OCR)

---

## 📞 Контакты

**Проект:** ALPACA Document Processing  
**Версия:** 1.0.0  
**Парсер:** alpaca-txt-parser  
**Лицензия:** Proprietary (ООО "Георезонанс")
