#!/usr/bin/env python3
"""
Оптимизированный PDF Parser

Полностью переписан с фокусом на скорость и качество.
- Минимум обращений к API/OCR
- Умная детекция типа документа
- Автоматический поворот только для перевёрнутых
- Русский язык везде
"""

import os
from pathlib import Path
from typing import TYPE_CHECKING

# Базовый парсер
from .base_parser import BaseParser

if TYPE_CHECKING:
    from utils.file_manager import File

# Импорты модулей
from .pdf_parser_module.orientation_detector import smart_rotate_pdf
from .pdf_parser_module.metadata_extractor import extract_pdf_metadata
from utils.logging import get_logger

# Импорты парсеров
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    from markitdown import MarkItDown
    MARKITDOWN_AVAILABLE = True
except ImportError:
    MARKITDOWN_AVAILABLE = False

try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False

try:
    from pdf2image import convert_from_path
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False

import requests
from settings import settings

logger = get_logger("alpaca.parser.pdf_optimized")


class OptimizedPDFParser(BaseParser):
    """
    Оптимизированный парсер PDF с умной обработкой
    
    Стратегия:
    1. Быстрая проверка ориентации (< 100ms для правильных документов)
    2. Поворот ТОЛЬКО если нужен
    3. Определение типа: текстовый vs отсканированный
    4. Выбор оптимального парсера
    """
    
    def __init__(self):
        super().__init__("pdf-optimized")
        self.unstructured_url = settings.UNSTRUCTURED_API_URL
    
    def parse(self, file: 'File') -> str:
        """
        Основной метод парсинга
        
        Args:
            file: Объект файла
            
        Returns:
            Распарсенный текст
        """
        file_path = file.full_path
        
        try:
            if not os.path.exists(file_path):
                self.logger.error(f"File not found | file={file.path}")
                return ""
            
            self.logger.info(f"🍎 Starting PDF parsing | file={file.path}")
            
            # Шаг 1: Извлечение метаданных
            metadata = extract_pdf_metadata(file_path)
            pages = metadata.get('pages', 0)
            self.logger.info(f"📄 PDF metadata | pages={pages}")
            
            # Шаг 2: Умная проверка ориентации + поворот если нужен
            working_file, needs_cleanup = smart_rotate_pdf(file_path)
            
            try:
                # Шаг 3: Определение типа документа
                doc_type, confidence = self._detect_document_type(working_file)
                self.logger.info(f"📋 Document type | type={doc_type} confidence={confidence}%")
                
                # Шаг 4: Парсинг по типу документа
                if doc_type == 'scanned':
                    text = self._parse_scanned(working_file)
                elif doc_type == 'text':
                    text = self._parse_text(working_file)
                else:  # hybrid
                    text = self._parse_hybrid(working_file)
                
                if not text:
                    self.logger.warning("All parsers failed, trying fallback")
                    text = self._parse_fallback(working_file)
                
                self.logger.info(f"✅ Parsing complete | length={len(text)} chars")
                return text
                
            finally:
                # Cleanup временного файла
                if needs_cleanup and os.path.exists(working_file):
                    try:
                        os.remove(working_file)
                    except:
                        pass
                        
        except Exception as e:
            self.logger.error(f"❌ Parsing failed | file={file.path} error={e}")
            return ""
    
    def _detect_document_type(self, file_path: str) -> tuple[str, int]:
        """
        Определяет тип документа: text, scanned или hybrid
        
        Returns:
            (type, confidence) - тип и уверенность 0-100
        """
        if not PYMUPDF_AVAILABLE:
            return 'hybrid', 50
        
        try:
            doc = fitz.open(file_path)
            page = doc[0]
            
            # Извлекаем текст
            text = page.get_text()
            text_len = len(text.strip())
            
            # Проверяем наличие изображений
            image_list = page.get_images()
            has_images = len(image_list) > 0
            
            doc.close()
            
            # Логика определения
            if text_len > 200:
                # Много текста = текстовый PDF
                return 'text', 90
            elif text_len < 50 and has_images:
                # Мало текста + есть изображения = отсканированный
                return 'scanned', 85
            elif text_len < 50:
                # Мало текста, нет изображений = возможно пустой или битый
                return 'scanned', 60
            else:
                # Средний объём текста = гибридный
                return 'hybrid', 70
                
        except Exception as e:
            self.logger.debug(f"Type detection failed | error={e}")
            return 'hybrid', 50
    
    def _parse_text(self, file_path: str) -> str:
        """Парсинг текстового PDF"""
        self.logger.debug("Using text parsing strategy")
        
        # Приоритет 1: Unstructured API (лучшее качество для таблиц)
        text = self._parse_with_unstructured(file_path)
        if text and len(text) > 100:
            return text
        
        # Приоритет 2: MarkItDown (быстро и надёжно)
        if MARKITDOWN_AVAILABLE:
            text = self._parse_with_markitdown(file_path)
            if text and len(text) > 100:
                return text
        
        # Приоритет 3: PyMuPDF (самый быстрый)
        if PYMUPDF_AVAILABLE:
            text = self._parse_with_pymupdf(file_path)
            if text:
                return text
        
        return ""
    
    def _parse_scanned(self, file_path: str) -> str:
        """Парсинг отсканированного PDF через OCR"""
        self.logger.debug("Using OCR strategy")
        
        # Приоритет 1: локальный OCR (быстрее, не требует сетевых вызовов)
        if PYTESSERACT_AVAILABLE and PDF2IMAGE_AVAILABLE:
            text = self._parse_with_tesseract(file_path)
            if text:
                return text
        else:
            if not PYTESSERACT_AVAILABLE:
                self.logger.debug("pytesseract not available, skipping local OCR")
            if not PDF2IMAGE_AVAILABLE:
                self.logger.debug("pdf2image not available, skipping local OCR")
        
        # Приоритет 2: Unstructured с OCR (hi_res стратегия)
        text = self._parse_with_unstructured(file_path, strategy='hi_res')
        return text if text else ""
    
    def _parse_hybrid(self, file_path: str) -> str:
        """Парсинг гибридного документа"""
        self.logger.debug("Using hybrid parsing strategy")
        
        # Пробуем как текстовый, потом как отсканированный
        text = self._parse_text(file_path)
        
        if not text or len(text) < 100:
            text = self._parse_scanned(file_path)
        
        return text
    
    def _parse_with_unstructured(self, file_path: str, strategy: str = 'hi_res') -> str:
        """Парсинг через Unstructured API с русским языком"""
        try:
            with open(file_path, 'rb') as f:
                response = requests.post(
                    self.unstructured_url,
                    files={'files': (os.path.basename(file_path), f, 'application/pdf')},
                    data={
                        'strategy': strategy,  # 'hi_res' для качества, 'fast' для скорости
                        'languages': 'rus',  # КРИТИЧНО: только rus! (rus+eng даёт транслитерацию)
                        'pdf_infer_table_structure': 'true',  # Таблицы
                    },
                    timeout=120
                )
            
            if response.status_code != 200:
                self.logger.warning(f"Unstructured API error | status={response.status_code}")
                return ""
            
            elements = response.json()
            
            # Собираем текст
            text_parts = []
            first_title = True
            
            for elem in elements:
                elem_type = elem.get('type', '')
                text = elem.get('text', '').strip()
                
                # Пропускаем изображения
                if elem_type == 'Image' or not text:
                    continue
                
                # Простое форматирование
                if elem_type == 'Title' and first_title and len(text) < 100:
                    text = f"# {text}"
                    first_title = False
                
                text_parts.append(text)
            
            result = '\n\n'.join(text_parts)
            self.logger.debug(f"Unstructured | elements={len(elements)} length={len(result)}")
            return result
            
        except Exception as e:
            self.logger.warning(f"Unstructured parsing failed | error={e}")
            return ""
    
    def _parse_with_markitdown(self, file_path: str) -> str:
        """Парсинг через MarkItDown"""
        try:
            md = MarkItDown()
            result = md.convert(file_path)
            text = result.text_content if hasattr(result, 'text_content') else str(result)
            self.logger.debug(f"MarkItDown | length={len(text)}")
            return text
        except Exception as e:
            self.logger.warning(f"MarkItDown failed | error={e}")
            return ""
    
    def _parse_with_pymupdf(self, file_path: str) -> str:
        """Быстрый парсинг через PyMuPDF"""
        try:
            doc = fitz.open(file_path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            self.logger.debug(f"PyMuPDF | length={len(text)}")
            return text
        except Exception as e:
            self.logger.warning(f"PyMuPDF failed | error={e}")
            return ""
    
    def _parse_fallback(self, file_path: str) -> str:
        """Последний резервный парсер"""
        try:
            from pypdf import PdfReader
            reader = PdfReader(file_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text()
            self.logger.debug(f"pypdf fallback | length={len(text)}")
            return text
        except Exception as e:
            self.logger.error(f"Fallback failed | error={e}")
            return ""

    def _parse_with_tesseract(self, file_path: str) -> str:
        """Локальный OCR через Tesseract с русским языком"""
        if not (PYTESSERACT_AVAILABLE and PDF2IMAGE_AVAILABLE):
            return ""
        
        try:
            # DPI 220 — баланс между качеством и скоростью
            images = convert_from_path(file_path, dpi=220)
        except Exception as e:
            self.logger.warning(f"pdf2image failed | error={e}")
            return ""
        
        if not images:
            self.logger.debug("pdf2image returned no pages")
            return ""
        
        text_parts: list[str] = []
        total_pages = len(images)
        
        for idx, img in enumerate(images, start=1):
            try:
                page_text = pytesseract.image_to_string(img, lang='rus', config='--psm 3')
                page_text = page_text.strip()
            except Exception as e:
                self.logger.debug(f"Tesseract failed on page {idx} | error={e}")
                continue
            
            if not page_text:
                continue
            
            ratio = self._calc_russian_ratio(page_text)
            self.logger.debug(
                f"OCR page {idx}/{total_pages} | chars={len(page_text)} russian={ratio:.1f}%"
            )
            text_parts.append(page_text)
        
        return '\n\n'.join(text_parts)
    
    @staticmethod
    def _calc_russian_ratio(text: str) -> float:
        alpha = sum(1 for c in text if c.isalpha())
        if alpha == 0:
            return 0.0
        russian = sum(1 for c in text if '\u0430' <= c.lower() <= '\u044f' or c in 'ёЁ')
        return russian / alpha * 100
