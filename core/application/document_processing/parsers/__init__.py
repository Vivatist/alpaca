"""
Коллекция парсеров документов.

=== НАЗНАЧЕНИЕ ===
Модуль экспортирует все доступные парсеры для извлечения текста
из различных форматов документов.

=== ПАРСЕРЫ ===
- BaseParser — базовый класс для всех парсеров
- WordParser — .doc, .docx (python-docx + MarkItDown + OCR)
- PDFParser — .pdf (PyMuPDF + Unstructured fallback)
- PowerPointParser — .ppt, .pptx (python-pptx)
- ExcelParser — .xls, .xlsx (openpyxl)
- TXTParser — .txt (chardet для кодировки)

=== ИСПОЛЬЗОВАНИЕ ===

    from core.application.document_processing.parsers import (
        WordParser, PDFParser, PowerPointParser, ExcelParser, TXTParser
    )
    from core.domain.files import FileSnapshot

    # Создать парсер
    parser = WordParser(enable_ocr=True)

    # Извлечь текст
    file = FileSnapshot(path="report.docx", hash="abc123")
    text = parser.parse(file)
    print(f"Extracted {len(text)} chars")

    # Или использовать через ParserRegistry
    from core.domain.document_processing import ParserRegistry
    registry = ParserRegistry(parsers={
        (".doc", ".docx"): WordParser(),
        (".pdf",): PDFParser(),
    })
    parser = registry.get_parser("report.docx")
    text = parser.parse(file)

=== СОЗДАНИЕ НОВОГО ПАРСЕРА ===

    from .base_parser import BaseParser

    class RTFParser(BaseParser):
        def __init__(self):
            super().__init__("rtf")

        def _parse(self, file: FileSnapshot) -> str:
            # Логика парсинга
            return extract_rtf_text(file.full_path)
"""

from .base_parser import BaseParser
from .word.word_parser import WordParser
from .pdf.pdf_parser import PDFParser
from .pptx.pptx_parser import PowerPointParser
from .excel.excel_parser import ExcelParser
from .txt.txt_parser import TXTParser

__all__ = [
    "BaseParser",
    "WordParser",
    "PDFParser",
    "PowerPointParser",
    "ExcelParser",
    "TXTParser",
]
