#!/usr/bin/env python3
"""Legacy compatibility wrapper for the optimized PDF parser."""

from app.parsers.pdf_parser_optimized import OptimizedPDFParser


class PDFParser(OptimizedPDFParser):
    """Thin wrapper preserved for backward-compatible imports."""

    def __init__(self, *_, **__):
        super().__init__()
        # Старый интерфейс экспонировал флаг enable_ocr — сохраняем его для кода,
        # который мог читать это свойство (например, таски в document-processors).
        self.enable_ocr = True
