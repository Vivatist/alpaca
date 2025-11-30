"""
Доменный протокол для парсеров документов.

=== НАЗНАЧЕНИЕ ===
Определяет контракт (Protocol) для всех парсеров документов.
Парсер извлекает текст из файла (DOCX, PDF, PPTX, XLS, TXT)
и возвращает его как строку (raw_text).

=== КОНТРАКТ ===

    class ParserProtocol(Protocol):
        def parse(self, file: FileSnapshot) -> str:
            ...

=== ИСПОЛЬЗОВАНИЕ ===

    from core.domain.document_processing.parsers import ParserProtocol
    from core.domain.files import FileSnapshot

    # Реализация парсера
    class MyParser:
        def parse(self, file: FileSnapshot) -> str:
            with open(file.full_path, 'r') as f:
                return f.read()

    # Типизация через Protocol (структурная, duck typing)
    def process(parser: ParserProtocol, file: FileSnapshot):
        text = parser.parse(file)
        print(f"Extracted {len(text)} chars")

    # Любой класс с методом parse() удовлетворяет протоколу
    parser = MyParser()
    process(parser, file)  # ✅ OK

=== РЕАЛИЗАЦИИ ===
См. core/application/document_processing/parsers/:
- WordParser (.doc, .docx)
- PDFParser (.pdf)
- PowerPointParser (.ppt, .pptx)
- ExcelParser (.xls, .xlsx)
- TXTParser (.txt)
"""

from __future__ import annotations

from typing import Protocol

from core.domain.files.models import FileSnapshot


class ParserProtocol(Protocol):
    """Структурный контракт для реализаций парсеров."""

    def parse(self, file: FileSnapshot) -> str:  # pragma: no cover - protocol definition
        ...


__all__ = ["ParserProtocol"]
