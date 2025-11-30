"""Parser interfaces re-exporting existing implementations."""

from app.parsers.base_parser import BaseParser
from app.parsers.word_parser_module.word_parser import WordParser
from app.parsers.pdf_parser_module.pdf_parser import PDFParser
from app.parsers.pptx_parser_module.pptx_parser import PowerPointParser
from app.parsers.excel_parser_module.excel_parser import ExcelParser
from app.parsers.txt_parser_module.txt_parser import TXTParser

__all__ = [
    "BaseParser",
    "WordParser",
    "PDFParser",
    "PowerPointParser",
    "ExcelParser",
    "TXTParser",
]
