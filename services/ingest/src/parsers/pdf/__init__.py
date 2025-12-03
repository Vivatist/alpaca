"""
PDF Parser — модуль для обработки PDF-документов.

=== НАЗНАЧЕНИЕ ===
Извлечение текста из PDF-файлов:
- Текстовые PDF — через PyMuPDF (быстро)
- Сканы/изображения — через Unstructured API (OCR)
- Автоматический fallback при малом количестве текста

=== СТЕК ТЕХНОЛОГИЙ ===
- PyMuPDF (fitz) — быстрый парсинг текста
- Unstructured API — OCR для сложных PDF

=== ЭКСПОРТЫ ===
- PDFParser — основной парсер
- extract_pdf_metadata — метаданные PDF (автор, дата, ...)
- smart_rotate_pdf — автоповорот страниц

=== ИСПОЛЬЗОВАНИЕ ===

        PDFParser, extract_pdf_metadata
    )
    from contracts import FileSnapshot

    # Парсинг PDF
    parser = PDFParser()
    file = FileSnapshot(path="report.pdf", hash="abc123")
    text = parser.parse(file)

    # Метаданные
    meta = extract_pdf_metadata("/path/to/file.pdf")
    print(meta)  # {'author': '...', 'created': '...'}

=== ЛОГИКА FALLBACK ===
Если PyMuPDF извлёк < 100 символов → Unstructured API (OCR)
"""

from .pdf_parser import PDFParser
from .metadata_extractor import extract_pdf_metadata
from .orientation_detector import smart_rotate_pdf

__all__ = ['PDFParser', 'extract_pdf_metadata', 'smart_rotate_pdf']
