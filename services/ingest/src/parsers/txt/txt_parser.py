#!/usr/bin/env python3
"""
TXT Parser для RAG системы ALPACA

Парсер текстовых файлов (.txt) с автоопределением кодировки.

Pipeline:
    .txt → Encoding Detection → Markdown

Возможности:
- Автоопределение кодировки (UTF-8, Windows-1251, etc.)
- Извлечение базовых метаданных (размер, дата модификации)
- Экспорт в Markdown формат для RAG индексации
"""

import os
from pathlib import Path
from typing import TYPE_CHECKING

from ..base_parser import BaseParser

if TYPE_CHECKING:
    from core.domain.files.models import FileSnapshot

# Импорты из модулей
from .encoding_detector import detect_encoding
from .text_formatter import format_as_markdown
from .metadata_extractor import extract_txt_metadata


class TXTParser(BaseParser):
    """
    Парсер текстовых файлов с автоопределением кодировки
    
    Использует pipeline:
    1. Автоопределение кодировки (chardet)
    2. Чтение контента
    3. Форматирование в Markdown
    """
    
    def __init__(self):
        """Инициализация парсера"""
        super().__init__("txt-parser")
    
    def _parse(self, file: 'FileSnapshot') -> str:
        """
        Парсинг TXT файла в текст
        
        Args:
            file: Объект File с информацией о файле
            
        Returns:
            str: Распарсенный текст документа (пустая строка при ошибке)
        """
        file_path = file.full_path
        file_hash = file.hash
        
        try:
            if not os.path.exists(file_path):
                self.logger.error(f"File not found | file={file.path}")
                raise FileNotFoundError(f"File not found | file={file.path}")
            
            self.logger.info(f"Parsing TXT document | file={file.path}")
            
            # 1. Добавляем ОБЩИЕ метаданные (в базовом классе)
            common_metadata = self._add_common_metadata(file_path, file_hash)
            
            # 2. Определение кодировки
            encoding = detect_encoding(file_path)
            self.logger.info(f"Detected encoding | encoding={encoding}")
            
            # 3. Чтение контента
            try:
                with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                    content = f.read()
            except Exception as e:
                self.logger.warning(f"Failed to read with {encoding}, trying UTF-8 | error={e}")
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                encoding = 'utf-8'
            
            if not content or not content.strip():
                self.logger.warning(f"Empty content | file={file_path}")
                raise ValueError(f"TXT file is empty | file={file_path}")
            
            # 4. Извлечение СПЕЦИФИЧНЫХ метаданных для TXT
            specific_metadata = extract_txt_metadata(encoding, content)
            
            self.logger.info(f"Metadata extracted | lines={specific_metadata.get('lines', 0)} chars={specific_metadata.get('characters', 0)}")
            
            # 5. Форматирование в Markdown
            markdown_content = format_as_markdown(content, Path(file_path).name)
            
            self.logger.info(f"TXT parsed successfully | file={file_path} content_length={len(markdown_content)}")

            return markdown_content

        except Exception as e:
            self.logger.error(f"TXT parsing failed | file={file_path} error={type(e).__name__}: {e}")
            raise
