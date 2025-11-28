"""
PDF Parser Module - модули для обработки PDF документов
"""

from .pdf_parser import PDFParser
from .metadata_extractor import extract_pdf_metadata
from .scan_detector import is_scanned_pdf
from .ocr_processor import parse_pdf_with_ocr
from .text_parser import parse_pdf_with_markitdown
from .fallback_parser import fallback_parse_pdf

__all__ = [
    'PDFParser',
    'extract_pdf_metadata',
    'is_scanned_pdf',
    'parse_pdf_with_ocr',
    'parse_pdf_with_markitdown',
    'fallback_parse_pdf',
]
