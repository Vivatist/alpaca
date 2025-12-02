# Application Document Processing

Конкретные **реализации** компонентов пайплайна обработки документов.

## Структура

```
application/document_processing/
├── parsers/      # WordParser, PDFParser, PowerPointParser, ExcelParser, TXTParser
├── cleaners/     # clean_text (simple_cleaner)
├── chunkers/     # chunk_document (custom_chunker)
└── embedders/    # custom_embedding (Ollama), langchain_embedding
```

## Реализации

### Парсеры (`parsers/`)
| Класс | Расширения | Технология |
|-------|------------|------------|
| `WordParser` | `.doc`, `.docx` | python-docx + MarkItDown + OCR |
| `PDFParser` | `.pdf` | PyMuPDF + fallback Unstructured |
| `PowerPointParser` | `.ppt`, `.pptx` | python-pptx |
| `ExcelParser` | `.xls`, `.xlsx` | openpyxl |
| `TXTParser` | `.txt` | chardet для кодировки |

### Клинеры (`cleaners/`)
- `clean_text` — удаление лишних пробелов, нормализация Unicode, управляющих символов

### Чанкеры (`chunkers/`)
- `chunk_document` — fixed-size chunking по 1000 символов с разбиением по параграфам

### Эмбеддеры (`embedders/`)
- `custom_embedding` — Ollama bge-m3 (бесплатно, локально)
- `langchain_embedding` — LangChain/OpenAI (платно)

## Использование

Реализации подключаются в `bootstrap.py`:

```python
from core.application.document_processing.parsers import WordParser, PDFParser
from core.application.document_processing.cleaners import clean_text
from core.application.document_processing.chunkers import chunk_document
from core.application.document_processing.embedders import custom_embedding

# Собираем пайплайн
ingest = IngestDocument(
    parser_registry=ParserRegistry({...}),
    cleaner=clean_text,
    chunker=chunk_document,
    embedder=custom_embedding,
)
```

## Настройки

- `ENABLE_CLEANER` — включить/выключить очистку текста
- `EMBEDDER_BACKEND` — `"custom"` (Ollama) или `"langchain"`

## Добавление новых реализаций

1. Создайте файл в соответствующей папке (например, `chunkers/semantic_chunker.py`)
2. Реализуйте функцию/класс, соответствующий контракту из `domain/`
3. Экспортируйте в `__init__.py`
4. Подключите в `bootstrap.py`
