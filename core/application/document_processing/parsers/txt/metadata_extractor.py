#!/usr/bin/env python3
"""
Metadata Extractor - извлечение метаданных из текстовых файлов

Извлекает специфичные для TXT метаданные (кодировка, строки, слова и т.д.)
"""

from typing import Dict

from utils.logging import get_logger

logger = get_logger("core.parser.txt_metadata_extractor")


def extract_txt_metadata(encoding: str, content: str) -> Dict:
    """
    Извлечение СПЕЦИФИЧНЫХ для TXT метаданных
    
    Общие метаданные (file_name, file_path, file_size, etc.) добавляются в базовом классе.
    Здесь добавляем только специфичные для текстовых файлов данные.
    
    Args:
        encoding: Кодировка файла
        content: Содержимое файла
        
    Returns:
        Dict со специфичными метаданными (encoding, lines, characters, words)
    """
    specific_metadata = {}
    
    try:
        # Специфичные для TXT метаданные
        specific_metadata['encoding'] = encoding
        specific_metadata['lines'] = len(content.splitlines())
        specific_metadata['characters'] = len(content)
        specific_metadata['words'] = len(content.split())
        
        logger.debug(f"TXT-specific metadata | encoding={encoding} lines={specific_metadata['lines']} words={specific_metadata['words']}")
        
    except Exception as e:
        logger.warning(f"Failed to extract TXT-specific metadata | error={type(e).__name__}: {e}")
    
    return specific_metadata
