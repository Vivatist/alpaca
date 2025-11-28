#!/usr/bin/env python3
"""
OCR Processor - обработка отсканированных PDF с OCR

Выполняет OCR для отсканированных PDF документов через Unstructured.
"""

try:
    from unstructured.partition.pdf import partition_pdf  # type: ignore
    UNSTRUCTURED_AVAILABLE = True
except ImportError:
    UNSTRUCTURED_AVAILABLE = False

from utils.logging import get_logger

logger = get_logger("alpaca.parser.pdf_ocr_processor")


def parse_pdf_with_ocr(file_path: str, ocr_strategy: str = "auto") -> str:
    """
    Парсинг PDF через OCR (для отсканированных документов)
    
    Использует Unstructured с поддержкой русского и английского языков
    
    Args:
        file_path: Путь к PDF файлу
        ocr_strategy: Стратегия OCR ('auto', 'hi_res', 'fast', 'ocr_only')
        
    Returns:
        Markdown текст с распознанным контентом
    """
    if not UNSTRUCTURED_AVAILABLE:
        logger.warning("Unstructured not available, cannot perform OCR")
        return ""
    
    try:
        logger.info(f"Starting OCR processing | strategy={ocr_strategy}")
        
        # Используем partition_pdf с OCR
        elements = partition_pdf(
            filename=file_path,
            strategy=ocr_strategy,
            infer_table_structure=True,
            languages=["rus", "eng"],  # КРИТИЧНО: русский + английский
            extract_images_in_pdf=True,  # Извлекать изображения
            max_partition=None  # Обрабатывать все страницы
        )
        
        if not elements:
            logger.warning("OCR returned no elements")
            return ""
        
        # Группируем элементы по страницам
        pages_content = {}
        current_page = 1
        
        for element in elements:
            # Проверяем метаданные страницы
            if hasattr(element, 'metadata') and hasattr(element.metadata, 'page_number'):
                page_num = element.metadata.page_number
            else:
                page_num = current_page
            
            if page_num not in pages_content:
                pages_content[page_num] = []
            
            element_text = str(element).strip()
            if element_text:
                pages_content[page_num].append(element_text)
            
            current_page = page_num
        
        # Собираем Markdown с разделением по страницам
        markdown_parts = []
        
        for page_num in sorted(pages_content.keys()):
            page_text = "\n\n".join(pages_content[page_num])
            if page_text:
                markdown_parts.append(f"## Страница {page_num}\n\n{page_text}")
        
        final_markdown = "\n\n".join(markdown_parts)
        
        logger.info(f"OCR processing complete | elements={len(elements)} pages={len(pages_content)} content_length={len(final_markdown)}")
        
        return final_markdown
        
    except Exception as e:
        logger.error(f"OCR processing failed | file={file_path} error={type(e).__name__}: {e}")
        return ""
