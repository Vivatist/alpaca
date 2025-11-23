# Text Cleaner Module

Модуль предварительной очистки текста перед записью в Markdown файлы для RAG индексации.

## Назначение

Исправляет проблемы кодировки и нормализует текст, извлеченный из документов:
- Mojibake (неправильная кодировка кириллицы)
- Unicode проблемы
- Лишние пробелы и переносы строк
- Невидимые символы
- Некорректная Markdown структура

## Использование

### В Celery тасках

```python
from text_cleaner import clean_markdown_text

# В таске перед записью на диск
markdown_content = parser.parse(file_path)
cleaned_content = clean_markdown_text(markdown_content)
markdown_writer.write(cleaned_content, output_path)
```

### Самостоятельное использование

```python
from text_cleaner import MarkdownCleaner

cleaner = MarkdownCleaner()

# Очистка с сохранением Markdown
text = "## Заголовок\n\nÐ ÑƒÑÑÐºÐ¸Ð¹   Ñ‚ÐµÐºÑÑ‚"
cleaned = cleaner.clean(text, preserve_markdown=True)
# Результат: "## Заголовок\n\nРусский текст\n"

# Очистка без Markdown (обычный текст)
cleaned = cleaner.clean(text, preserve_markdown=False)
```

## Pipeline очистки

```
Raw MD text
    ↓
ftfy.fix_text() - исправление кодировки
    ↓
cleantext.clean() - нормализация
    ↓
_clean_markdown_specific() - Markdown форматирование
    ↓
Clean MD text
```

## Зависимости

- **ftfy** (>= 6.1.0): исправление mojibake, Unicode нормализация
- **clean-text** (>= 0.6.0): продвинутая текстовая нормализация

Оба пакета опциональны - если недоступны, текст возвращается без изменений.

## Что исправляется

### Проблемы кодировки (ftfy)
- `Ð ÑƒÑÑÐºÐ¸Ð¹` → `Русский`
- `â€œquotesâ€` → `"quotes"`
- Ligatures: `ﬁle` → `file`
- Fullwidth: `Ｈｅｌｌｏ` → `Hello`
- ANSI escape codes: `\x1b[31mRed\x1b[0m` → `Red`

### Нормализация (clean-text)
- Multiple spaces: `text    text` → `text text`
- Unicode fixes: smart quotes, dashes, etc.
- Preserves Cyrillic, numbers, punctuation, URLs

### Markdown специфика
- Multiple newlines: `\n\n\n\n` → `\n\n`
- Trailing spaces: `text   \n` → `text\n`
- Header spacing: `##Header` → `## Header`
- Separators: `---` → `\n---\n`

## Параметры

### `clean_markdown_text(text, preserve_markdown=True, skip_if_unavailable=True)`

- `text`: исходный Markdown текст
- `preserve_markdown`: сохранять Markdown разметку (заголовки, списки, таблицы)
- `skip_if_unavailable`: если библиотеки недоступны, вернуть исходный текст

## Производительность

- Minimal overhead: ~10-50ms для типичного документа (10KB)
- No blocking I/O: только CPU-bound операции
- Thread-safe: использует singleton pattern

## Примеры проблем

### До очистки
```markdown
##Заголовок


Ð ÑƒÑÑÐºÐ¸Ð¹   Ñ‚ÐµÐºÑÑ‚    Ñ   Ð¿Ñ€Ð¾Ð±Ð»ÐµÐ¼Ð°Ð¼Ð¸   
---
Еще    текст


```

### После очистки
```markdown
## Заголовок

Русский текст с проблемами

---

Еще текст
```

## Интеграция

Модуль интегрируется в существующий pipeline документ-процессоров:

```
Document → Parser → Raw MD → Text Cleaner → Clean MD → Markdown Writer → Disk
```

Вызывается в тасках (`pdf_tasks.py`, `word_tasks.py`, etc.) перед `markdown_writer.write()`.
