"""Thin compatibility package for PDF parser helpers."""

from .metadata_extractor import extract_pdf_metadata
from .orientation_detector import smart_rotate_pdf

__all__ = ['PDFParser', 'extract_pdf_metadata', 'smart_rotate_pdf']


def __getattr__(name):
    if name == 'PDFParser':
        from .pdf_parser import PDFParser  # noqa: WPS433 - lazy import to avoid cycles
        return PDFParser
    raise AttributeError(name)
