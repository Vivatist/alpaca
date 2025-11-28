#!/usr/bin/env python3
"""
Fallback Parser - резервный парсер PDF через pypdf

Простое извлечение текста когда другие методы недоступны.
"""

try:
    import pypdf  # type: ignore
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

from utils.logging import get_logger

logger = get_logger("alpaca.parser.pdf_fallback")


def fallback_parse_pdf(file_path: str) -> str:
    """
    Резервный парсер через pypdf
    
    Args:
        file_path: Путь к PDF файлу
        
    Returns:
        Простой текст документа
    """
    if not PYPDF_AVAILABLE:
        logger.error("pypdf not available, cannot parse PDF")
        return "ERROR: No parser available (install markitdown or pypdf)"
    
    try:
        with open(file_path, 'rb') as f:
            pdf_reader = pypdf.PdfReader(f)
            
            pages_text = []
            
            for page_num, page in enumerate(pdf_reader.pages, 1):
                text = page.extract_text() or ""
                if text.strip():
                    pages_text.append(f"## Страница {page_num}\n\n{text.strip()}")
            
            return "\n\n".join(pages_text)
            
    except Exception as e:
        logger.error(f"Fallback parser failed | error={e}")
        return f"ERROR: Failed to parse PDF: {str(e)}"
