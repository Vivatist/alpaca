#!/usr/bin/env python3
"""
Text Parser - парсинг текстовых PDF

Парсит PDF документы с извлекаемым текстом.
Приоритет: PyMuPDF (лучше для русского) → Markitdown → pypdf
"""

import re

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    from markitdown import MarkItDown  # type: ignore
    MARKITDOWN_AVAILABLE = True
except ImportError:
    MARKITDOWN_AVAILABLE = False

from utils.logging import get_logger
from settings import settings
import requests
import os

from .pdf_rotator import auto_rotate_before_parsing

logger = get_logger("alpaca.parser.pdf_text_parser")





def parse_pdf_with_unstructured(file_path: str, as_markdown: bool = True) -> str:
    """
    Парсинг PDF через Unstructured API
    
    Использует стратегию 'hi_res' для таблиц и сложных документов.
    Автоматически исправляет ориентацию перевёрнутых страниц.
    
    Args:
        file_path: Путь к PDF файлу
        as_markdown: Применить базовое Markdown форматирование
        
    Returns:
        Текст с сохранением структуры (опционально с Markdown)
    """
    try:
        # Автоматически исправляем ориентацию если нужно
        working_file, needs_cleanup = auto_rotate_before_parsing(file_path)
        
        with open(working_file, 'rb') as f:
            response = requests.post(
                settings.UNSTRUCTURED_API_URL,
                files={'files': (file_path.split('/')[-1], f, 'application/pdf')},
                data={
                    'strategy': 'hi_res',  # Высокое разрешение для таблиц
                    'languages': 'rus',  # Чисто русский язык — исключает латинскую транслитерацию
                    'pdf_infer_table_structure': 'true',  # Распознавание структуры таблиц
                    'extract_image_block_types': 'Table',  # Извлекать таблицы
                    'skip_infer_table_types': '[]',  # Не пропускать таблицы
                },
                timeout=120
            )
        
        if response.status_code != 200:
            logger.error(f"Unstructured API error | status={response.status_code}")
            return ""
        
        elements = response.json()
        
        # Фильтруем Image элементы и собираем текст
        text_parts = []
        first_title = True
        
        for elem in elements:
            elem_type = elem.get('type', '')
            text = elem.get('text', '').strip()
            
            # Пропускаем Image элементы (обычно мусор от OCR логотипов)
            if elem_type == 'Image':
                continue
            
            if not text:
                continue
            
            # Минимальное Markdown форматирование - только первый заголовок
            if as_markdown and elem_type == 'Title' and first_title and len(text) < 80:
                text = f"# {text}"
                first_title = False
            
            text_parts.append(text)
        
        result = '\n\n'.join(text_parts)
        logger.debug(f"Unstructured parsing complete | elements={len(elements)} text_parts={len(text_parts)} markdown={as_markdown} length={len(result)}")
        
        # Удаляем временный файл если был создан
        if needs_cleanup and os.path.exists(working_file):
            try:
                os.remove(working_file)
            except:
                pass
        
        return result
        
    except Exception as e:
        logger.error(f"Unstructured parsing failed | file={file_path} error={e}")
        
        # Удаляем временный файл если был создан
        if 'needs_cleanup' in locals() and needs_cleanup and 'working_file' in locals() and os.path.exists(working_file):
            try:
                os.remove(working_file)
            except:
                pass
        
        return ""


def parse_pdf_with_pymupdf(file_path: str) -> str:
    """
    Парсинг PDF через PyMuPDF (лучше для русского языка)
    
    Args:
        file_path: Путь к PDF файлу
        
    Returns:
        Текст из PDF как есть
    """
    if not PYMUPDF_AVAILABLE:
        logger.debug("PyMuPDF not available")
        return ""
    
    try:
        doc = fitz.open(file_path)
        text_parts = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            if text.strip():
                text_parts.append(text)
        
        doc.close()
        
        full_text = '\n\n'.join(text_parts)
        
        logger.debug(f"PyMuPDF parsing complete | pages={len(text_parts)} length={len(full_text)}")
        
        return full_text
        
    except Exception as e:
        logger.error(f"PyMuPDF parsing failed | error={e}")
        return ""


def _convert_to_markdown(text: str) -> str:
    """
    Простое преобразование plain text в Markdown
    
    - Bullet points (•) → - 
    - Первая строка документа → # (главный заголовок)
    - Короткие строки с заглавными буквами → ##
    
    Args:
        text: Plain text из PDF
        
    Returns:
        Markdown форматированный текст
    """
    lines = text.split('\n')
    markdown_lines = []
    first_non_empty = True
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        if not stripped:
            markdown_lines.append('')
            continue
        
        # Первая непустая строка - главный заголовок
        if first_non_empty:
            # Если это не bullet и не слишком длинная строка
            if not stripped.startswith('•') and len(stripped) < 80:
                markdown_lines.append(f"# {stripped}")
                first_non_empty = False
                continue
            first_non_empty = False
        
        # Bullet points
        if stripped.startswith('•'):
            markdown_lines.append(stripped.replace('•', '-', 1))
        # Короткие строки с двоеточием в конце или заглавными (вероятно подзаголовки)
        elif (len(stripped) < 60 and 
              (stripped.endswith(':') or 
               (stripped[0].isupper() and i > 0 and not lines[i-1].strip()))):
            markdown_lines.append(f"## {stripped}")
        else:
            markdown_lines.append(stripped)
    
    return '\n'.join(markdown_lines)


def parse_pdf_with_markitdown(file_path: str) -> str:
    """
    Парсинг PDF через Markitdown (дефолтные настройки)
    
    Использует pdfminer под капотом с оптимальными настройками по умолчанию
    
    Args:
        file_path: Путь к PDF файлу
        
    Returns:
        Текст с сохранением структуры
    """
    if not MARKITDOWN_AVAILABLE:
        logger.warning("Markitdown not available")
        return ""
    
    try:
        # Используем MarkItDown с настройками по умолчанию
        markitdown = MarkItDown()
        result = markitdown.convert(file_path)
        text = result.text_content if hasattr(result, 'text_content') else str(result)
        
        logger.debug(f"Markitdown parsing complete | length={len(text)}")
        return text
        
    except Exception as e:
        logger.error(f"Markitdown parsing failed | error={e}")
        return ""
