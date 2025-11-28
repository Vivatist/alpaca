#!/usr/bin/env python3
"""
Text Parser - парсинг текстовых PDF через Markitdown

Парсит PDF документы с извлекаемым текстом.
"""

try:
    from markitdown import MarkItDown  # type: ignore
    MARKITDOWN_AVAILABLE = True
except ImportError:
    MARKITDOWN_AVAILABLE = False

from utils.logging import get_logger

logger = get_logger("alpaca.parser.pdf_text_parser")


def parse_pdf_with_markitdown(file_path: str) -> str:
    """
    Парсинг PDF через Markitdown (для текстовых PDF)
    
    Args:
        file_path: Путь к PDF файлу
        
    Returns:
        Markdown текст
    """
    if not MARKITDOWN_AVAILABLE:
        logger.warning("Markitdown not available")
        return ""
    
    try:
        markitdown = MarkItDown()
        result = markitdown.convert(file_path)
        markdown = result.text_content if hasattr(result, 'text_content') else str(result)
        
        logger.debug(f"Markitdown parsing complete | length={len(markdown)}")
        
        return markdown
        
    except Exception as e:
        logger.error(f"Markitdown parsing failed | error={e}")
        return ""
