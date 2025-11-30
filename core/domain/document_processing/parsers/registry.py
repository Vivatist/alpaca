"""Parser registry for mapping file extensions to parsers."""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from . import ParserProtocol


class ParserRegistry:
    """Maps file extensions to parser instances."""

    def __init__(self, parsers: Dict[Tuple[str, ...], ParserProtocol]):
        """
        Args:
            parsers: Dict mapping extension tuples to parser instances
                    Example: {('.doc', '.docx'): word_parser, ('.pdf',): pdf_parser}
        """
        self._parsers = parsers

    def get_parser(self, file_path: str) -> Optional[ParserProtocol]:
        """Returns parser for file extension or None if unsupported."""
        lower_path = file_path.lower()
        for extensions, parser in self._parsers.items():
            if lower_path.endswith(extensions):
                return parser
        return None


__all__ = ["ParserRegistry"]
