"""
Word Parser Module - модули для обработки Word документов
"""

from .image_converter import convert_wmf_to_png, extract_images_via_pdf, get_image_extension
from .ocr_processor import extract_images_from_docx, process_images_with_ocr
from .metadata_extractor import extract_word_metadata
from ..document_converter import convert_doc_to_docx
from .fallback_parser import fallback_parse, table_to_markdown

__all__ = [
    'convert_wmf_to_png',
    'extract_images_via_pdf',
    'get_image_extension',
    'extract_images_from_docx',
    'process_images_with_ocr',
    'extract_word_metadata',
    'convert_doc_to_docx',
    'fallback_parse',
    'table_to_markdown',
]
