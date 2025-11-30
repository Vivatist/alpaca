"""Parser interfaces re-exporting application-layer implementations."""

from alpaca.application.document_processing.parsers import (
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
