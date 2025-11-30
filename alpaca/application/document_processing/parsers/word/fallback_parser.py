#!/usr/bin/env python3
"""
Fallback Parser - альтернативные методы парсинга Word

Резервный парсер через python-docx или olefile для старых форматов.
"""

from pathlib import Path
from typing import TYPE_CHECKING
from docx import Document  # type: ignore
from docx.oxml.table import CT_Tbl  # type: ignore
from docx.oxml.text.paragraph import CT_P  # type: ignore
from docx.table import Table  # type: ignore
from docx.text.paragraph import Paragraph  # type: ignore

from utils.logging import get_logger

if TYPE_CHECKING:
    from docx.table import Table

logger = get_logger("alpaca.parser.fallback_parser")


def fallback_parse(file_path: str) -> str:
    """
    Резервный парсер через python-docx или antiword для .doc
    
    Args:
        file_path: Путь к файлу
        
    Returns:
        Простой текст документа
    """
    file_ext = Path(file_path).suffix.lower()
    
    # Для .doc файлов сначала пробуем olefile
    if file_ext == '.doc':
        logger.info("Fallback parser: trying olefile for .doc file")
        try:
            import olefile # type: ignore
            if olefile.isOleFile(file_path):
                ole = olefile.OleFileIO(file_path)
                if ole.exists('WordDocument'):
                    word_stream = ole.openstream('WordDocument').read()
                    # Простое извлечение текста (наивный подход)
                    text = word_stream.decode('latin-1', errors='ignore')
                    # Фильтруем печатные символы
                    text = ''.join(c for c in text if c.isprintable() or c in '\n\r\t')
                    ole.close()
                    if len(text) > 100:
                        logger.info(f"Olefile successful | length={len(text)}")
                        return text
                else:
                    logger.warning("WordDocument stream not found")
        except Exception as e:
            logger.warning(f"Olefile error | error={type(e).__name__}: {e}")
        
        # Если olefile не сработал, возвращаем ошибку
        return f"ERROR: Cannot parse old .doc format. Please convert to .docx manually."
    
    # Для .docx используем python-docx
    try:
        doc = Document(file_path)
        paragraphs = []
        
        for element in doc.element.body:
            if isinstance(element, CT_P):
                para = Paragraph(element, doc)
                if para.text.strip():
                    # Сохраняем заголовки
                    if para.style.name.startswith('Heading'):
                        level = para.style.name.replace('Heading ', '')
                        if level.isdigit():
                            paragraphs.append(f"{'#' * int(level)} {para.text}")
                        else:
                            paragraphs.append(f"**{para.text}**")
                    else:
                        paragraphs.append(para.text)
                        
            elif isinstance(element, CT_Tbl):
                table = Table(element, doc)
                paragraphs.append(table_to_markdown(table))
        
        return "\n\n".join(paragraphs)
        
    except Exception as e:
        logger.error(f"Fallback parser failed | error={type(e).__name__}: {e}")
        return f"ERROR: Failed to parse document: {str(e)}"


def table_to_markdown(table: 'Table') -> str:
    """
    Конвертация таблицы Word в Markdown
    
    Args:
        table: Объект Table из python-docx
        
    Returns:
        Таблица в формате Markdown
    """
    if not table.rows:
        return ""
    
    lines = []
    
    # Заголовок таблицы (первая строка)
    header_cells = [cell.text.strip() for cell in table.rows[0].cells]
    lines.append("| " + " | ".join(header_cells) + " |")
    lines.append("|" + "|".join(["---"] * len(header_cells)) + "|")
    
    # Остальные строки
    for row in table.rows[1:]:
        cells = [cell.text.strip() for cell in row.cells]
        lines.append("| " + " | ".join(cells) + " |")
    
    return "\n".join(lines)
