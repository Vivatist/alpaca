#!/usr/bin/env python3
"""
Scan Detector - определение отсканированных PDF документов

Определяет является ли PDF текстовым или отсканированным.
"""

try:
    import pypdf  # type: ignore
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

from utils.logging import get_logger

logger = get_logger("alpaca.parser.scan_detector")


def is_scanned_pdf(file_path: str) -> bool:
    """
    Определение - текстовый или отсканированный PDF
    
    Стратегия:
    - Извлекаем текст с первых 3 страниц
    - Если текста < 50 символов на страницу → отсканированный
    
    Args:
        file_path: Путь к PDF файлу
        
    Returns:
        True если отсканированный (нужен OCR), False если текстовый
    """
    if not PYPDF_AVAILABLE:
        logger.warning("pypdf not available, assuming scanned PDF")
        return True  # По умолчанию считаем отсканированным
    
    try:
        with open(file_path, 'rb') as f:
            pdf_reader = pypdf.PdfReader(f)
            
            # Проверяем первые 3 страницы
            pages_to_check = min(3, len(pdf_reader.pages))
            total_text = ""
            
            for i in range(pages_to_check):
                page = pdf_reader.pages[i]
                text = page.extract_text() or ""
                total_text += text
            
            # Если в среднем < 50 символов на страницу - это скан
            avg_chars_per_page = len(total_text.strip()) / pages_to_check if pages_to_check > 0 else 0
            is_scanned = avg_chars_per_page < 50
            
            logger.debug(f"Scanned detection | avg_chars_per_page={avg_chars_per_page:.1f} is_scanned={is_scanned}")
            
            return is_scanned
            
    except Exception as e:
        logger.warning(f"Scanned detection failed | error={e} defaulting_to_scanned=true")
        return True
