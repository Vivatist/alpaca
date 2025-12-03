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

        WordParser, PDFParser, PowerPointParser, ExcelParser, TXTParser
    )
    from contracts import FileSnapshot

    # Создать парсер
    parser = WordParser(enable_ocr=True)

    # Извлечь текст
    file = FileSnapshot(path="report.docx", hash="abc123")
    text = parser.parse(file)
    print(f"Extracted {len(text)} chars")

    # Или использовать через ParserRegistry
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

from typing import Dict, Tuple, Optional
from contracts import FileSnapshot


class ParserRegistry:
    """Реестр парсеров по расширениям файлов."""
    
    def __init__(self, parsers: Dict[Tuple[str, ...], BaseParser]):
        self._parsers = parsers
        self._ext_map: Dict[str, BaseParser] = {}
        for extensions, parser in parsers.items():
            for ext in extensions:
                self._ext_map[ext.lower()] = parser
    
    def get_parser(self, file_path: str) -> Optional[BaseParser]:
        """Получить парсер по расширению файла."""
        import os
        ext = os.path.splitext(file_path)[1].lower()
        return self._ext_map.get(ext)
    
    def supported_extensions(self) -> list:
        """Список поддерживаемых расширений."""
        return list(self._ext_map.keys())
    
    def parse(self, file: FileSnapshot) -> str:
        """Парсинг файла через соответствующий парсер."""
        parser = self.get_parser(file.path)
        if not parser:
            raise ValueError(f"No parser found for: {file.path}")
        return parser.parse(file)


def build_parser_registry() -> ParserRegistry:
    """Создать реестр парсеров с настройками по умолчанию."""
    return ParserRegistry({
        (".doc", ".docx"): WordParser(enable_ocr=True),
        (".pdf",): PDFParser(),
        (".ppt", ".pptx"): PowerPointParser(),
        (".xls", ".xlsx"): ExcelParser(),
        (".txt",): TXTParser(),
    })


__all__ = [
    "BaseParser",
    "WordParser",
    "PDFParser",
    "PowerPointParser",
    "ExcelParser",
    "TXTParser",
    "ParserRegistry",
    "build_parser_registry",
]
