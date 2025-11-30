"""Parser interfaces re-exporting application-layer implementations."""

from core.application.document_processing.parsers import (
    BaseParser,
    WordParser,
    PDFParser,
    PowerPointParser,
    ExcelParser,
    TXTParser,
)

__all__ = [
    "BaseParser",
    "WordParser",
    "PDFParser",
    "PowerPointParser",
    "ExcelParser",
    "TXTParser",
]
