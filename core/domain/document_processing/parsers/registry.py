"""Parser registry exposed at domain level."""

from __future__ import annotations

from typing import Callable, Optional, Tuple

from . import (
    BaseParser,
    WordParser,
    PDFParser,
    PowerPointParser,
    ExcelParser,
    TXTParser,
)


def _reuse(parser: BaseParser) -> Callable[[], BaseParser]:
    return lambda parser=parser: parser


class ParserRegistry:
    """Simple factory that returns parser instances by file extension."""

    def __init__(self, registry: Optional[Tuple[Tuple[Tuple[str, ...], Callable[[], BaseParser]], ...]] = None):
        if registry is not None:
            self._registry = registry
        else:
            self._registry = (
                ((".docx", ".doc"), _reuse(WordParser(enable_ocr=True))),
                ((".pdf",), _reuse(PDFParser())),
                ((".pptx", ".ppt"), _reuse(PowerPointParser())),
                ((".xlsx", ".xls"), _reuse(ExcelParser())),
                ((".txt",), _reuse(TXTParser())),
            )

    def get_parser(self, file_path: str) -> Optional[BaseParser]:
        lower_path = file_path.lower()
        for extensions, factory in self._registry:
            if lower_path.endswith(extensions):
                return factory()
        return None


parser_registry = ParserRegistry()
get_parser_for_path = parser_registry.get_parser

__all__ = ["ParserRegistry", "parser_registry", "get_parser_for_path"]
