"""
TXT Parser Module - модули для обработки текстовых файлов
"""

from .txt_parser import TXTParser
from .encoding_detector import detect_encoding
from .text_formatter import format_as_markdown
from .metadata_extractor import extract_txt_metadata

__all__ = [
    'TXTParser',
    'detect_encoding',
    'format_as_markdown',
    'extract_txt_metadata',
]
