#!/usr/bin/env python3
"""
Оптимизированный PDF Parser

Находится в pdf_parser_module ради обратной совместимости, но содержит
современную реализацию с локальным OCR и умной обработкой.
"""

import os
import re
from typing import TYPE_CHECKING

from ..base_parser import BaseParser
from .orientation_detector import smart_rotate_pdf
from .metadata_extractor import extract_pdf_metadata
from utils.logging import get_logger
from settings import settings

if TYPE_CHECKING:  # pragma: no cover - только для type checkers
    from utils.file_manager import File


import fitz  # PyMuPDF
from markitdown import MarkItDown
import pytesseract
from pdf2image import convert_from_path

import requests

logger = get_logger("alpaca.parser.pdf")


class PDFParser(BaseParser):
    """Оптимизированный парсер PDF с умной обработкой."""

    def __init__(self):
        super().__init__("pdf-optimized")
        self.unstructured_url = settings.UNSTRUCTURED_API_URL
        # Свойство использовалось в старой версии — сохраняем для совместимости
        self.enable_ocr = True

    def parse(self, file: 'File') -> str:
        file_path = file.full_path

        try:
            if not os.path.exists(file_path):
                self.logger.error(f"File not found | file={file.path}")
                return ""

            self.logger.info(f"🍎 Starting PDF parsing | file={file.path}")

            metadata = extract_pdf_metadata(file_path)
            pages = metadata.get('pages', 0)
            self.logger.info(f"📄 PDF metadata | pages={pages}")

            working_file, needs_cleanup = smart_rotate_pdf(file_path)

            try:
                doc_type, confidence = self._detect_document_type(working_file)
                self.logger.info(f"📋 Document type | type={doc_type} confidence={confidence}%")

                if doc_type == 'scanned':
                    text = self._parse_scanned(working_file)
                elif doc_type == 'text':
                    text = self._parse_text(working_file)
                else:
                    text = self._parse_hybrid(working_file)

                if not text:
                    self.logger.warning("All parsers failed, trying fallback")
                    text = self._parse_fallback(working_file)

                self.logger.info(f"✅ Parsing complete | length={len(text)} chars")
                return text

            finally:
                if needs_cleanup and os.path.exists(working_file):
                    try:
                        os.remove(working_file)
                    except OSError:
                        pass

        except Exception as e:  # pragma: no cover - защитный блок
            self.logger.error(f"❌ Parsing failed | file={file.path} error={e}")
            return ""

    def _detect_document_type(self, file_path: str) -> tuple[str, int]:
        try:
            doc = fitz.open(file_path)
            page = doc[0]

            text = page.get_text()
            text_len = len(text.strip())
            has_images = len(page.get_images()) > 0
            doc.close()

            if text_len > 200:
                return 'text', 90
            if text_len < 50 and has_images:
                return 'scanned', 85
            if text_len < 50:
                return 'scanned', 60
            return 'hybrid', 70

        except Exception as e:  # pragma: no cover
            self.logger.debug(f"Type detection failed | error={e}")
            return 'hybrid', 50

    def _parse_text(self, file_path: str) -> str:
        self.logger.debug("Using text parsing strategy")

        best_candidate = ""

        text = self._parse_with_unstructured(file_path)
        if text:
            if self._is_text_quality_ok(text):
                return text
            best_candidate = text

        text = self._parse_with_markitdown(file_path)
        if text:
            if self._is_text_quality_ok(text):
                return text
            if not best_candidate:
                best_candidate = text

        text = self._parse_with_pymupdf(file_path)
        if text:
            if self._is_text_quality_ok(text):
                return text
            if not best_candidate:
                best_candidate = text

        return best_candidate

    def _parse_scanned(self, file_path: str) -> str:
        self.logger.debug("Using OCR strategy")

        ocr_text = self._parse_with_tesseract(file_path)
        if ocr_text and self._is_text_quality_ok(ocr_text):
            return ocr_text

        text = self._parse_with_unstructured(file_path, strategy='hi_res')
        if text and self._is_text_quality_ok(text):
            return text

        return text or ocr_text or ""

    def _parse_hybrid(self, file_path: str) -> str:
        self.logger.debug("Using hybrid parsing strategy")
        text = self._parse_text(file_path)
        if not text or len(text) < 100:
            text = self._parse_scanned(file_path)
        return text

    def _parse_with_unstructured(self, file_path: str, strategy: str = 'hi_res') -> str:
        try:
            with open(file_path, 'rb') as f:
                response = requests.post(
                    self.unstructured_url,
                    files={'files': (os.path.basename(file_path), f, 'application/pdf')},
                    data={
                        'strategy': strategy,
                        'languages': 'rus',  # чисто русский язык
                        'pdf_infer_table_structure': 'true',
                    },
                    timeout=120,
                )

            if response.status_code != 200:
                self.logger.warning(f"Unstructured API error | status={response.status_code}")
                return ""

            elements = response.json()
            text_parts: list[str] = []
            first_title = True

            for elem in elements:
                elem_type = elem.get('type', '')
                text = elem.get('text', '').strip()

                if elem_type == 'Image' or not text:
                    continue

                if elem_type == 'Title' and first_title and len(text) < 100:
                    text = f"# {text}"
                    first_title = False

                text_parts.append(text)

            result = '\n\n'.join(text_parts)
            self.logger.debug(f"Unstructured | elements={len(elements)} length={len(result)}")
            return result

        except Exception as e:  # pragma: no cover
            self.logger.warning(f"Unstructured parsing failed | error={e}")
            return ""

    def _parse_with_markitdown(self, file_path: str) -> str:
        try:
            md = MarkItDown()
            result = md.convert(file_path)
            text = result.text_content if hasattr(result, 'text_content') else str(result)
            self.logger.debug(f"MarkItDown | length={len(text)}")
            return text
        except Exception as e:  # pragma: no cover
            self.logger.warning(f"MarkItDown failed | error={e}")
            return ""

    def _parse_with_pymupdf(self, file_path: str) -> str:
        try:
            doc = fitz.open(file_path)
            text = ''.join(page.get_text() for page in doc)
            doc.close()
            self.logger.debug(f"PyMuPDF | length={len(text)}")
            return text
        except Exception as e:  # pragma: no cover
            self.logger.warning(f"PyMuPDF failed | error={e}")
            return ""

    def _parse_fallback(self, file_path: str) -> str:
        try:
            from pypdf import PdfReader

            reader = PdfReader(file_path)
            text = ''.join((page.extract_text() or '') for page in reader.pages)
            self.logger.debug(f"pypdf fallback | length={len(text)}")
            return text
        except Exception as e:  # pragma: no cover
            self.logger.error(f"Fallback failed | error={e}")
            return ""

    def _parse_with_tesseract(self, file_path: str) -> str:
        try:
            images = convert_from_path(file_path, dpi=220)
        except Exception as e:
            self.logger.warning(f"pdf2image failed | error={e}")
            return ""

        if not images:
            self.logger.debug("pdf2image returned no pages")
            return ""

        text_parts: list[str] = []
        total_pages = len(images)

        for idx, img in enumerate(images, start=1):
            try:
                page_text = pytesseract.image_to_string(
                    img,
                    lang='rus+eng',
                    config='--psm 6'
                ).strip()
            except Exception as e:
                self.logger.debug(f"Tesseract failed on page {idx} | error={e}")
                continue

            if not page_text:
                continue

            ratio = self._calc_russian_ratio(page_text)
            self.logger.debug(
                f"OCR page {idx}/{total_pages} | chars={len(page_text)} russian={ratio:.1f}%"
            )
            text_parts.append(page_text)

        return '\n\n'.join(text_parts)

    @staticmethod
    def _is_text_quality_ok(text: str) -> bool:
        if not text:
            return False

        cleaned = text.strip()
        if len(cleaned) < 400:
            return False

        tokens = [token for token in re.split(r"\s+", cleaned) if token]
        if len(tokens) < 40:
            return False

        short_tokens = sum(1 for token in tokens if len(token) == 1)
        if short_tokens / len(tokens) > 0.35:
            return False

        return True

    @staticmethod
    def _calc_russian_ratio(text: str) -> float:
        alpha = sum(1 for c in text if c.isalpha())
        if alpha == 0:
            return 0.0
        russian = sum(1 for c in text if '\u0430' <= c.lower() <= '\u044f' or c in 'ёЁ')
        return russian / alpha * 100
