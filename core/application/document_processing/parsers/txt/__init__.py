"""
TXT Parser — модуль для обработки текстовых файлов.

=== НАЗНАЧЕНИЕ ===
Извлечение текста из .txt файлов:
- Автоопределение кодировки (UTF-8, CP1251, ...)
- Форматирование в Markdown
- Извлечение метаданных

=== СТЕК ТЕХНОЛОГИЙ ===
- chardet — определение кодировки

=== ЭКСПОРТЫ ===
- TXTParser — основной парсер
- detect_encoding — определение кодировки файла
- format_as_markdown — форматирование текста
- extract_txt_metadata — метаданные файла

=== ИСПОЛЬЗОВАНИЕ ===

    from core.application.document_processing.parsers.txt import (
        TXTParser, detect_encoding
    )
    from core.domain.files import FileSnapshot

    # Парсинг TXT
    parser = TXTParser()
    file = FileSnapshot(path="readme.txt", hash="abc123")
    text = parser.parse(file)

    # Определить кодировку
    encoding = detect_encoding("/path/to/file.txt")
    print(encoding)  # 'utf-8' или 'cp1251'
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
