#!/usr/bin/env python3
"""PowerPoint parser with PPT->PPTX conversion and structured Markdown output."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from pptx import Presentation
from pptx.enum.shapes import PP_PLACEHOLDER

try:  # Optional dependency — fallback only
    from unstructured.partition.pptx import partition_pptx
    UNSTRUCTURED_AVAILABLE = True
except Exception:  # pragma: no cover - optional import
    partition_pptx = None
    UNSTRUCTURED_AVAILABLE = False

from ..base_parser import BaseParser
from ..document_converter import convert_ppt_to_pptx

if TYPE_CHECKING:  # pragma: no cover
    from alpaca.domain.files.models import FileSnapshot


class PowerPointParser(BaseParser):
    """Парсер PowerPoint презентаций (.ppt/.pptx) с поддержкой конверсии."""

    def __init__(self) -> None:
        super().__init__("powerpoint-parser")

    def _parse(self, file: "FileSnapshot") -> str:
        file_path = file.full_path
        working_path = file_path
        cleanup_dir: Optional[Path] = None

        try:
            if not os.path.exists(file_path):
                self.logger.error(f"File not found | file={file.path}")
                raise FileNotFoundError(f"File not found | file={file.path}")

            self.logger.info(f"Parsing PowerPoint document | file={file.path}")

            suffix = Path(file_path).suffix.lower()
            if suffix == ".ppt":
                converted = convert_ppt_to_pptx(file_path)
                if converted:
                    working_path = converted
                    cleanup_dir = Path(converted).parent
                    self.logger.info("Converted legacy .ppt to .pptx via LibreOffice")
                else:
                    self.logger.warning("Failed to convert .ppt, attempting fallback parsing")

            text = self._parse_with_python_pptx(working_path)
            if text.strip():
                return text

            self.logger.warning("python-pptx returned empty output, using Unstructured fallback")
            text = self._parse_with_unstructured(working_path)
            return text.strip()

        except Exception as e:  # pragma: no cover - защитный блок
            self.logger.error(f"PowerPoint parsing failed | file={file.path} error={type(e).__name__}: {e}")
            raise
        finally:
            if cleanup_dir and cleanup_dir.exists():
                shutil.rmtree(cleanup_dir, ignore_errors=True)

    def _parse_with_python_pptx(self, pptx_path: str) -> str:
        try:
            presentation = Presentation(pptx_path)
        except Exception as e:
            self.logger.warning(f"python-pptx failed | file={pptx_path} error={type(e).__name__}: {e}")
            return ""

        slide_blocks: List[str] = []
        for index, slide in enumerate(presentation.slides, start=1):
            content = self._extract_slide_content(slide)
            if not content:
                continue
            slide_blocks.append("\n\n".join([f"## Слайд {index}"] + content))

        result = "\n\n---\n\n".join(slide_blocks)
        self.logger.info(f"python-pptx parsing complete | slides={len(slide_blocks)} length={len(result)}")
        return result

    def _extract_slide_content(self, slide) -> List[str]:
        lines: List[str] = []
        for shape in slide.shapes:
            lines.extend(self._extract_shape_content(shape))
        return lines

    def _extract_shape_content(self, shape) -> List[str]:
        lines: List[str] = []

        if getattr(shape, "has_text_frame", False):
            text_lines = self._text_frame_to_markdown(shape)
            if text_lines:
                lines.extend(text_lines)

        if getattr(shape, "has_table", False):
            table_md = self._table_to_markdown(shape.table)
            if table_md:
                lines.append(table_md)

        nested_shapes = getattr(shape, "shapes", None)
        if nested_shapes:
            for nested in nested_shapes:
                lines.extend(self._extract_shape_content(nested))

        return lines

    def _text_frame_to_markdown(self, shape) -> List[str]:
        lines: List[str] = []

        try:
            paragraphs = shape.text_frame.paragraphs
        except AttributeError:
            return lines

        placeholder_type = self._get_placeholder_type(shape)

        if placeholder_type in {PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE}:
            for paragraph in paragraphs:
                text = paragraph.text.strip()
                if text:
                    lines.append(f"### {text}")
            return lines

        if placeholder_type == PP_PLACEHOLDER.SUBTITLE:
            for paragraph in paragraphs:
                text = paragraph.text.strip()
                if text:
                    lines.append(f"#### {text}")
            return lines

        for paragraph in paragraphs:
            text = paragraph.text.strip()
            if not text:
                continue
            level = getattr(paragraph, "level", 0) or 0
            level = max(0, min(level, 6))
            indent = "  " * level
            bullet = "-" if level == 0 else "*"
            lines.append(f"{indent}{bullet} {text}")

        return lines

    @staticmethod
    def _get_placeholder_type(shape) -> Optional[int]:
        if getattr(shape, "is_placeholder", False):
            try:
                return shape.placeholder_format.type
            except Exception:  # pragma: no cover
                return None
        return None

    def _table_to_markdown(self, table) -> str:
        try:
            rows = list(table.rows)
        except AttributeError:
            return ""

        if not rows:
            return ""

        header = [self._clean_cell_text(cell.text) for cell in rows[0].cells]
        divider = "|" + "|".join(["---"] * len(header)) + "|"

        body_rows: List[str] = []
        for row in rows[1:]:
            cells = [self._clean_cell_text(cell.text) for cell in row.cells]
            body_rows.append("| " + " | ".join(cells) + " |")

        header_line = "| " + " | ".join(header) + " |"
        return "\n".join([header_line, divider, *body_rows])

    @staticmethod
    def _clean_cell_text(text: str) -> str:
        return (text or "").replace("\n", " ").strip()

    def _parse_with_unstructured(self, pptx_path: str) -> str:
        if not UNSTRUCTURED_AVAILABLE or partition_pptx is None:
            self.logger.warning("Unstructured partition for PPTX is not available")
            return ""

        try:
            elements = partition_pptx(
                filename=pptx_path,
                infer_table_structure=True,
                languages=["rus", "eng"],
            )
        except Exception as e:
            self.logger.warning(f"Unstructured fallback failed | file={pptx_path} error={type(e).__name__}: {e}")
            return ""

        if not elements:
            return ""

        sections: List[str] = []
        current_slide = None
        buffer: List[str] = []

        for element in elements:
            text = str(element).strip()
            if not text:
                continue

            metadata = getattr(element, "metadata", None)
            slide_number = getattr(metadata, "page_number", None) if metadata else None

            if slide_number is not None and slide_number != current_slide:
                if buffer:
                    sections.append("\n\n".join(buffer))
                    buffer = []
                current_slide = slide_number
                buffer.append(f"## Слайд {slide_number}")

            buffer.append(text)

        if buffer:
            sections.append("\n\n".join(buffer))

        result = "\n\n---\n\n".join(sections)
        self.logger.info(f"Unstructured fallback complete | slides={len(sections)} length={len(result)}")
        return result


class PptxParser(PowerPointParser):
    """Обратная совместимость с историческим именем."""


__all__ = ["PowerPointParser", "PptxParser"]
