# Domain Document Processing

Доменный слой определяет **контракты** (интерфейсы) для компонентов пайплайна обработки документов.

## Структура

```
domain/document_processing/
├── parsers/      # ParserProtocol, ParserRegistry
├── cleaners/     # Cleaner (type alias)
├── chunkers/     # Chunker (type alias)
└── embedders/    # Embedder (type alias)
```

## Контракты

| Контракт | Сигнатура | Назначение |
|----------|-----------|------------|
| `ParserProtocol` | `parse(FileSnapshot) -> str` | Извлечение текста из файла |
| `ParserRegistry` | `get_parser(path) -> Parser` | Реестр парсеров по расширениям |
| `Cleaner` | `(FileSnapshot) -> str` | Очистка/нормализация текста |
| `Chunker` | `(FileSnapshot) -> List[str]` | Разбиение на чанки |
| `Embedder` | `(FileRepository, FileSnapshot, List[str]) -> int` | Создание эмбеддингов |

## Использование

```python
from core.domain.document_processing import (
    ParserProtocol, ParserRegistry, Cleaner, Chunker, Embedder
)

# Типизация зависимостей в use-case
@dataclass
class IngestDocument:
    parser_registry: ParserRegistry
    cleaner: Optional[Cleaner]
    chunker: Chunker
    embedder: Embedder
```

## Принципы

- **Домен не знает о реализациях** — только контракты
- **Реализации в application/** — `parsers/`, `cleaners/`, `chunkers/`, `embedders/`
- **Связывание в bootstrap** — `build_worker_application()` подключает реализации
- **Направленность зависимостей**: `domain ← application ← infrastructure`
