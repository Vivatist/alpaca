#!/usr/bin/env python3
"""
PDF Parser для RAG системы ALPACA

Парсер PDF документов с OCR поддержкой для отсканированных страниц.

Pipeline:
    .pdf → Markitdown + Unstructured OCR → Текст

Возможности:
- Извлечение текста с сохранением структуры
- OCR для отсканированных страниц и встроенных изображений
- Извлечение метаданных (автор, дата создания, количество страниц)
- Экспорт текста для RAG индексации
"""

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

# Добавляем путь к базовому парсеру
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from base_parser import BaseParser

if TYPE_CHECKING:
    from utils.file_manager import File

# Импорты из модулей
from .metadata_extractor import extract_pdf_metadata
from .scan_detector import is_scanned_pdf
from .ocr_processor import parse_pdf_with_ocr
from .text_parser import parse_pdf_with_markitdown
from .fallback_parser import fallback_parse_pdf


class PDFParser(BaseParser):
    """
    Парсер PDF документов с поддержкой OCR
    
    Использует pipeline:
    1. Markitdown - основной парсер для текстовых PDF
    2. pypdf - извлечение метаданных
    3. Unstructured - OCR для отсканированных PDF (стратегия hi_res)
    4. Автоопределение типа PDF (текстовый vs отсканированный)
    """
    
    def __init__(self, enable_ocr: bool = True, ocr_strategy: str = "auto"):
        """
        Инициализация парсера
        
        Args:
            enable_ocr: Включить OCR для отсканированных страниц
            ocr_strategy: Стратегия OCR ('auto', 'hi_res', 'fast', 'ocr_only')
        """
        super().__init__("pdf-parser")
        self.enable_ocr = enable_ocr
        self.ocr_strategy = ocr_strategy
    
    def parse(self, file: 'File') -> str:
        """
        Парсинг PDF документа в текст
        
        Args:
            file: Объект File с информацией о файле
            
        Returns:
            str: Распарсенный текст документа (пустая строка при ошибке)
        """
        file_path = file.path
        file_hash = file.hash
        
        try:
            if not os.path.exists(file_path):
                self.logger.error(f"File not found | file={file_path}")
                return ""
            
            self.logger.info(f"Parsing PDF document | file={file_path}")
            
            # 1. Добавляем ОБЩИЕ метаданные (в базовом классе)
            common_metadata = self._add_common_metadata(file_path, file_hash)
            
            # 2. Извлечение СПЕЦИФИЧНЫХ метаданных PDF через pypdf
            specific_metadata = extract_pdf_metadata(file_path)
            
            self.logger.info(f"Metadata extracted | pages={specific_metadata.get('pages', 0)} author={specific_metadata.get('author', 'Unknown')}")
            
            # 3. Проверка - текстовый или отсканированный PDF
            is_scanned = is_scanned_pdf(file_path)
            self.logger.info(f"PDF type detected | scanned={is_scanned} ocr_enabled={self.enable_ocr}")
            
            # 4. Основной парсинг
            if is_scanned and self.enable_ocr:
                # Отсканированный PDF - используем OCR
                self.logger.info(f"Processing as scanned PDF with OCR | strategy={self.ocr_strategy}")
                markdown_content = parse_pdf_with_ocr(file_path, self.ocr_strategy)
                
                # Fallback если OCR не дал результата
                if not markdown_content or len(markdown_content.strip()) < 50:
                    self.logger.warning("OCR produced little content, trying fallback")
                    markdown_content = fallback_parse_pdf(file_path)
            else:
                # Текстовый PDF - используем Markitdown
                self.logger.info("Processing as text-based PDF with Markitdown")
                markdown_content = parse_pdf_with_markitdown(file_path)
                
                # Fallback если Markitdown не сработал
                if not markdown_content:
                    self.logger.warning("Markitdown failed, using fallback parser")
                    markdown_content = fallback_parse_pdf(file_path)
                
                # Если текста мало и OCR включен - дополнительно запустим OCR
                elif self.enable_ocr and len(markdown_content.strip()) < 100:
                    self.logger.warning(f"Low text content detected | length={len(markdown_content)} running_ocr=true")
                    ocr_content = parse_pdf_with_ocr(file_path, self.ocr_strategy)
                    if ocr_content and len(ocr_content) > len(markdown_content):
                        self.logger.info(f"OCR produced more content | ocr_length={len(ocr_content)} text_length={len(markdown_content)}")
                        markdown_content = ocr_content
            
            self.logger.info(f"PDF parsed successfully | file={file_path} content_length={len(markdown_content)}")
            
            return markdown_content
            
        except Exception as e:
            self.logger.error(f"PDF parsing failed | file={file_path} error={type(e).__name__}: {e}")
            return ""
