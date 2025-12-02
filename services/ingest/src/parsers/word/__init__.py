"""
Word Parser — модуль для обработки Word-документов.

=== НАЗНАЧЕНИЕ ===
Извлечение текста из .doc и .docx файлов:
- Текст из параграфов
- Текст из таблиц
- OCR для изображений внутри документа
- Конвертация .doc → .docx

=== СТЕК ТЕХНОЛОГИЙ ===
- MarkItDown — быстрая конвертация в Markdown
- python-docx — глубокий разбор структуры
- pytesseract — OCR для изображений
- libreoffice — конвертация .doc → .docx

=== ЭКСПОРТЫ ===
- convert_wmf_to_png — конвертация WMF-изображений
- extract_images_via_pdf — извлечение изображений через PDF
- get_image_extension — определение формата изображения
- extract_images_from_docx — извлечение встроенных изображений
- process_images_with_ocr — OCR обработка
- extract_word_metadata — метаданные документа
- convert_doc_to_docx — конвертация старого формата
- fallback_parse — запасной парсинг
- table_to_markdown — таблицы в Markdown

=== ИСПОЛЬЗОВАНИЕ ===

    from core.application.document_processing.parsers.word import (
        extract_images_from_docx, process_images_with_ocr
    )

    # Извлечь изображения и прогнать OCR
    images = extract_images_from_docx("report.docx")
    ocr_text = process_images_with_ocr(images)

Главный парсер: WordParser в word_parser.py
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
