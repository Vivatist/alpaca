#!/usr/bin/env python3
"""
Text Formatter - форматирование текста в Markdown

Конвертирует обычный текст в структурированный Markdown.
"""

from pathlib import Path

from utils.logging import get_logger

logger = get_logger("core.parser.text_formatter")


def format_as_markdown(content: str, filename: str) -> str:
    """
    Форматирование текста как Markdown
    
    Добавляет заголовок и сохраняет структуру текста
    
    Args:
        content: Текстовое содержимое
        filename: Имя файла для заголовка
        
    Returns:
        Markdown текст
    """
    # Заголовок документа
    title = Path(filename).stem.replace('_', ' ')
    markdown_lines = [f"# {title}", ""]
    
    # Разбиваем на абзацы (двойные переводы строк)
    paragraphs = content.split('\n\n')
    
    for para in paragraphs:
        # Убираем лишние пробелы, но сохраняем структуру
        para = para.strip()
        if para:
            markdown_lines.append(para)
            markdown_lines.append("")  # Пустая строка между абзацами
    
    return "\n".join(markdown_lines)
