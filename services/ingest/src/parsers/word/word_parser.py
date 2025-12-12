#!/usr/bin/env python3
"""
Word Document Parser для RAG системы ALPACA

Парсер Word документов (.doc, .docx) с OCR поддержкой для отсканированных страниц.

Pipeline:
    .docx/.doc → Markitdown + Unstructured OCR → Markdown + YAML metadata

Возможности:
- Извлечение текста с сохранением структуры (заголовки, списки, таблицы)
- OCR для встроенных изображений (отсканированные документы)
- Извлечение метаданных (автор, дата создания, количество страниц)
- Генерация YAML header с метаданными
- Экспорт в Markdown формат для RAG индексации
"""

import os
import shutil
import re
from pathlib import Path
from typing import TYPE_CHECKING

from ..base_parser import BaseParser

if TYPE_CHECKING:
    from contracts import FileSnapshot

from markitdown import MarkItDown  # type: ignore

# Импорты из модулей
from ..document_converter import convert_doc_to_docx
from .metadata_extractor import extract_word_metadata
from .ocr_processor import extract_images_from_docx, process_images_with_ocr
from .fallback_parser import fallback_parse


class WordParser(BaseParser):
    """
    Парсер Word документов с поддержкой OCR
    
    Использует pipeline:
    1. Markitdown - основной парсер структуры документа
    2. python-docx - извлечение метаданных и изображений
    3. Unstructured - OCR для изображений (отсканированные страницы)
    4. YAML header - метаданные для RAG
    """
    
    def __init__(self, enable_ocr: bool = True, ocr_strategy: str = "auto"):
        """
        Инициализация парсера
        
        Args:
            enable_ocr: Включить OCR для изображений
            ocr_strategy: Стратегия OCR ('auto', 'hi_res', 'fast')
        """
        super().__init__("word-parser")
        self.enable_ocr = enable_ocr
        self.ocr_strategy = ocr_strategy
        
        # Инициализация Markitdown
        self.markitdown = MarkItDown()
    
    def _parse(self, file: 'FileSnapshot') -> str:
        """
        Парсинг Word документа в текст
        
        Args:
            file: Объект File с информацией о файле
            
        Returns:
            str: Распарсенный текст документа (пустая строка при ошибке)
        """
        converted = False
        file_path = file.full_path
        file_hash = file.hash
        
        try:
            if not os.path.exists(file_path):
                self.logger.error(f"File not found")
                raise FileNotFoundError(f"File not found | file={file_path}")
            
            self.logger.info(f"Word parsing | ext={Path(file_path).suffix.lower()}")
            
            # 1. Конвертация .doc → .docx через LibreOffice если нужно
            file_ext = Path(file_path).suffix.lower()
            original_file_path = file_path
            
            if file_ext == '.doc':
                self.logger.info(f"Old .doc format detected, converting to .docx via LibreOffice")
                converted_path = convert_doc_to_docx(file_path)
                if converted_path:
                    file_path = converted_path
                    file_ext = '.docx'
                    converted = True
                    self.logger.info(f"Converted .doc to .docx")
                else:
                    self.logger.warning(f"Failed to convert .doc to .docx, will try direct parsing")
            
            # 2. Извлечение СПЕЦИФИЧНЫХ метаданных Word через python-docx (только для .docx)
            specific_metadata = {}
            
            if file_ext == '.docx':
                try:
                    specific_metadata = extract_word_metadata(file_path)
                except Exception as e:
                    self.logger.warning(f"Failed to extract Word-specific metadata | error={type(e).__name__}: {e}")
                    if converted:
                        self.logger.info(f"Converted .docx appears corrupted, using fallback parser on original .doc")
                        file_path = original_file_path
                        file_ext = '.doc'
            
            # 3. Основной парсинг через Markitdown
            markdown_content = self._parse_with_markitdown(file_path)
            
            # 4. OCR для изображений (если включено и это .docx)
            if self.enable_ocr and file_ext == '.docx':
                self.logger.info(f"Processing document with OCR | enable_ocr={self.enable_ocr}")
                
                # Извлекаем изображения
                images_info = extract_images_from_docx(file_path)
                self.logger.info(f"Images extracted | count={len(images_info)}")
                
                if images_info:
                    self.logger.info(f"Starting OCR processing | images={len(images_info)}")
                    
                    # Получаем OCR текст для каждого изображения
                    ocr_texts = process_images_with_ocr(images_info, self.ocr_strategy)
                    
                    if ocr_texts:
                        # Заменяем base64 изображения на OCR текст в правильном порядке
                        image_pattern = r'!\[\]\(data:image/[^)]+\)'
                        
                        def replace_image(match):
                            nonlocal ocr_texts
                            if ocr_texts:
                                return ocr_texts.pop(0)
                            return match.group(0)
                        
                        markdown_content = re.sub(image_pattern, replace_image, markdown_content)
                        self.logger.info(f"OCR content inserted | replaced_images={len(images_info) - len(ocr_texts)}")
                    else:
                        self.logger.warning("OCR processing returned no content")
                else:
                    self.logger.info("No images found in document for OCR")
            elif not self.enable_ocr:
                self.logger.debug("OCR disabled, skipping image processing")
            
            self.logger.info(f"Word parsed | chars={len(markdown_content)}")

            return markdown_content

        except Exception as e:
            self.logger.error(f"Error parsing Word | error={type(e).__name__}: {e}")
            raise
        
        finally:
            # Очистка временных файлов после конвертации
            if converted:
                try:
                    converted_dir = Path(file_path).parent
                    if converted_dir.name.startswith("alpaca_doc_convert_"):
                        shutil.rmtree(converted_dir)
                        self.logger.info(f"Cleaned up temp conversion directory | dir={converted_dir}")
                except Exception as e:
                    self.logger.warning(f"Failed to clean up temp directory | error={e}")
    
    def _parse_with_markitdown(self, file_path: str) -> str:
        """
        Парсинг Word через Markitdown
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            Markdown текст
        """
        try:
            self.logger.debug(f"Parsing with markitdown")
            result = self.markitdown.convert(file_path)
            
            if result and hasattr(result, 'text_content'):
                markdown_text = result.text_content
                self.logger.info(f"Markitdown successful | length={len(markdown_text)}")
                return markdown_text
            else:
                self.logger.warning(f"Markitdown returned empty or invalid result")
                return self._fallback_parse_internal(file_path)
                
        except Exception as e:
            self.logger.error(f"Markitdown failed | error={type(e).__name__}: {e}")
            return self._fallback_parse_internal(file_path)
    
    def _fallback_parse_internal(self, file_path: str) -> str:
        """Внутренний вызов fallback парсера"""
        self.logger.info(f"Using fallback parser")
        return fallback_parse(file_path)
