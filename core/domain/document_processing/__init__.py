"""
Доменные типы и контракты для обработки документов.

=== НАЗНАЧЕНИЕ ===
Модуль экспортирует интерфейсы (протоколы и type aliases) для компонентов
пайплайна обработки документов:
- ParserProtocol — контракт для парсеров (DOCX, PDF, etc.)
- ParserRegistry — реестр парсеров по расширениям файлов
- Chunker — type alias для функции разбиения текста на чанки
- Embedder — type alias для функции создания эмбеддингов

=== АРХИТЕКТУРА ===
Домен определяет КОНТРАКТЫ, а не реализации:

    # Домен (контракт)
    Chunker = Callable[[FileSnapshot], List[str]]

    # Application (реализация)
    def chunking(file: FileSnapshot) -> List[str]:
        return file.raw_text.split(...)

=== ИСПОЛЬЗОВАНИЕ ===

    from core.domain.document_processing import (
        ParserProtocol, ParserRegistry, Chunker, Embedder
    )

    # Типизация зависимостей в use-case
    @dataclass
    class IngestDocument:
        parser_registry: ParserRegistry
        chunker: Chunker      # Callable[[FileSnapshot], List[str]]
        embedder: Embedder    # Callable[[FileRepository, FileSnapshot, List[str]], int]

        def __call__(self, file: FileSnapshot) -> bool:
            parser = self.parser_registry.get_parser(file.path)
            file.raw_text = parser.parse(file)
            chunks = self.chunker(file)
            count = self.embedder(self.repository, file, chunks)
            return count > 0

=== СИГНАТУРЫ ===
- Chunker: (FileSnapshot) -> List[str]
- Embedder: (FileRepository, FileSnapshot, List[str]) -> int
- ParserProtocol.parse: (FileSnapshot) -> str
"""

from .parsers import ParserProtocol
from .parsers.registry import ParserRegistry
from .cleaners import Cleaner
from .chunkers import Chunker
from .embedders import Embedder

__all__ = [
    "ParserProtocol",
    "ParserRegistry",
    "Chunker",
    "Cleaner",
    "Embedder",
]
