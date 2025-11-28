#!/usr/bin/env python3
"""
PDF Parser для RAG системы ALPACA

Парсер PDF документов с OCR поддержкой для отсканированных страниц.

Pipeline:
    .pdf → Markitdown + Unstructured OCR → Markdown + YAML metadata

Возможности:
- Извлечение текста с сохранением структуры
- OCR для отсканированных страниц и встроенных изображений
- Извлечение метаданных (автор, дата создания, количество страниц)
- Генерация YAML header с метаданными
- Экспорт в Markdown формат для RAG индексации
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime

# Добавляем путь к базовому парсеру
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from base_parser import BaseParser

try:
    from markitdown import MarkItDown  # type: ignore
    MARKITDOWN_AVAILABLE = True
except ImportError:
    MARKITDOWN_AVAILABLE = False

try:
    from unstructured.partition.pdf import partition_pdf  # type: ignore
    UNSTRUCTURED_AVAILABLE = True
except ImportError:
    UNSTRUCTURED_AVAILABLE = False

try:
    import pypdf # type: ignore
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

try:
    from pdf2image import convert_from_path  # type: ignore
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class PDFParser(BaseParser):
    """
    Парсер PDF документов с поддержкой OCR
    
    Использует pipeline:
    1. Markitdown - основной парсер для текстовых PDF
    2. pypdf - извлечение метаданных
    3. Unstructured - OCR для отсканированных PDF (стратегия hi_res)
    4. pdf2image - конвертация страниц в изображения для OCR
    5. YAML header - метаданные для RAG
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
        
        # Проверка зависимостей
        self._check_dependencies()
        
        # Инициализация Markitdown
        if MARKITDOWN_AVAILABLE:
            self.markitdown = MarkItDown()
        else:
            self.markitdown = None
            
    def _check_dependencies(self):
        """Проверка наличия необходимых библиотек"""
        missing = []
        
        if not MARKITDOWN_AVAILABLE:
            missing.append("markitdown")
        if not PYPDF_AVAILABLE:
            missing.append("pypdf")
        if self.enable_ocr and not UNSTRUCTURED_AVAILABLE:
            missing.append("unstructured[all-docs]")
        if self.enable_ocr and not PDF2IMAGE_AVAILABLE:
            missing.append("pdf2image")
            
        if missing:
            self.logger.warning(f"Missing dependencies | packages={', '.join(missing)}")
    
    def parse(self, file_path: str, file_hash: Optional[str] = None) -> Dict:
        """
        Парсинг PDF документа в Markdown с метаданными
        
        Args:
            file_path: Путь к .pdf файлу
            file_hash: Хэш файла от file-watcher (опционально)
            
        Returns:
            Dict с ключами:
                - markdown: str - Текст в Markdown формате
                - metadata: Dict - Метаданные документа
                - pages_info: List[Dict] - Информация о страницах
                - yaml_header: str - YAML header для документа
                - success: bool - Статус парсинга
                - error: Optional[str] - Сообщение об ошибке
        """
        result = {
            'markdown': '',
            'metadata': {},
            'pages_info': [],
            'yaml_header': '',
            'success': False,
            'error': None
        }
        
        try:
            if not os.path.exists(file_path):
                result['error'] = f"File not found: {file_path}"
                return result
            
            self.logger.info(f"Parsing PDF document | file={file_path}")
            
            # 1. Добавляем ОБЩИЕ метаданные (в базовом классе)
            common_metadata = self._add_common_metadata(file_path, file_hash)
            
            # 2. Извлечение СПЕЦИФИЧНЫХ метаданных PDF через pypdf
            specific_metadata = self._extract_pdf_specific_metadata(file_path)
            
            self.logger.info(f"Metadata extracted | pages={specific_metadata.get('pages', 0)} author={specific_metadata.get('author', 'Unknown')}")
            
            # 3. Проверка - текстовый или отсканированный PDF
            is_scanned = self._is_scanned_pdf(file_path)
            self.logger.info(f"PDF type detected | scanned={is_scanned} ocr_enabled={self.enable_ocr}")
            
            # Добавляем is_scanned в специфичные метаданные
            specific_metadata['is_scanned'] = is_scanned
            
            # 4. Основной парсинг
            if is_scanned and self.enable_ocr:
                # Отсканированный PDF - используем OCR
                self.logger.info(f"Processing as scanned PDF with OCR | strategy={self.ocr_strategy}")
                markdown_content = self._parse_with_ocr(file_path)
                specific_metadata['ocr_enabled'] = True
                specific_metadata['ocr_strategy'] = self.ocr_strategy
            else:
                # Текстовый PDF - используем Markitdown
                self.logger.info("Processing as text-based PDF with Markitdown")
                markdown_content = self._parse_with_markitdown(file_path)
                
                # Если текста мало и OCR включен - дополнительно запустим OCR
                if self.enable_ocr and len(markdown_content.strip()) < 100:
                    self.logger.warning(f"Low text content detected | length={len(markdown_content)} running_ocr=true")
                    ocr_content = self._parse_with_ocr(file_path)
                    if ocr_content and len(ocr_content) > len(markdown_content):
                        self.logger.info(f"OCR produced more content | ocr_length={len(ocr_content)} text_length={len(markdown_content)}")
                        markdown_content = ocr_content
                        specific_metadata['ocr_enabled'] = True
                        specific_metadata['ocr_strategy'] = self.ocr_strategy
                    else:
                        specific_metadata['ocr_enabled'] = False
                else:
                    specific_metadata['ocr_enabled'] = False
            
            result['markdown'] = markdown_content
            
            # 5. Объединяем все метаданные для результата
            result['metadata'] = {**common_metadata, **specific_metadata}
            
            # 6. Генерация YAML header с разделением общих и специфичных метаданных
            yaml_header = self._generate_yaml_header(
                common_metadata,
                specific_metadata,
                'pdf'
            )
            result['yaml_header'] = yaml_header
            
            result['success'] = True
            
            self.logger.info(f"PDF parsed successfully | file={file_path} content_length={len(markdown_content)}")
            
        except Exception as e:
            result['error'] = str(e)
            result['success'] = False
            self.logger.error(f"PDF parsing failed | file={file_path} error={type(e).__name__}: {e}")
        
        return result
    
    def _extract_pdf_specific_metadata(self, file_path: str) -> Dict:
        """
        Извлечение СПЕЦИФИЧНЫХ для PDF метаданных
        
        Общие метаданные (file_name, file_path, file_size, etc.) добавляются в базовом классе.
        Здесь добавляем только специфичные для PDF данные.
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            Dict со специфичными метаданными
        """
        specific_metadata = {
            'pages': 0,
            'author': '',
            'subject': '',
            'creator': '',
            'producer': '',
            'encrypted': False
        }
        
        if not PYPDF_AVAILABLE:
            return specific_metadata
        
        try:
            with open(file_path, 'rb') as f:
                pdf_reader = pypdf.PdfReader(f)
                
                # Базовая информация
                specific_metadata['pages'] = len(pdf_reader.pages)
                specific_metadata['encrypted'] = pdf_reader.is_encrypted
                
                # Метаданные из PDF Info
                if pdf_reader.metadata:
                    info = pdf_reader.metadata
                    
                    # Конвертируем pypdf объекты в обычные строки
                    author = info.get('/Author', '')
                    specific_metadata['author'] = str(author) if author else ''
                    
                    subject = info.get('/Subject', '')
                    specific_metadata['subject'] = str(subject) if subject else ''
                    
                    creator = info.get('/Creator', '')
                    specific_metadata['creator'] = str(creator) if creator else ''
                    
                    producer = info.get('/Producer', '')
                    specific_metadata['producer'] = str(producer) if producer else ''
                
                self.logger.debug(f"PDF-specific metadata | pages={specific_metadata['pages']} author={specific_metadata['author']}")
                
        except Exception as e:
            self.logger.warning(f"PDF-specific metadata extraction failed | file={file_path} error={type(e).__name__}: {e}")
        
        return specific_metadata
    
    def _is_scanned_pdf(self, file_path: str) -> bool:
        """
        Определение - текстовый или отсканированный PDF
        
        Стратегия:
        - Извлекаем текст с первых 3 страниц
        - Если текста < 50 символов на страницу → отсканированный
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            True если отсканированный (нужен OCR)
        """
        if not PYPDF_AVAILABLE:
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
                avg_chars_per_page = len(total_text.strip()) / pages_to_check
                is_scanned = avg_chars_per_page < 50
                
                self.logger.debug(f"Scanned detection | avg_chars_per_page={avg_chars_per_page:.1f} is_scanned={is_scanned}")
                
                return is_scanned
                
        except Exception as e:
            self.logger.warning(f"Scanned detection failed | error={e} defaulting_to_scanned=true")
            return True
    
    def _parse_with_markitdown(self, file_path: str) -> str:
        """
        Парсинг PDF через Markitdown (для текстовых PDF)
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            Markdown текст
        """
        if not MARKITDOWN_AVAILABLE or not self.markitdown:
            self.logger.warning("Markitdown not available, using fallback")
            return self._fallback_parse(file_path)
        
        try:
            result = self.markitdown.convert(file_path)
            markdown = result.text_content if hasattr(result, 'text_content') else str(result)
            
            self.logger.debug(f"Markitdown parsing complete | length={len(markdown)}")
            
            return markdown
            
        except Exception as e:
            self.logger.error(f"Markitdown parsing failed | error={e}")
            return self._fallback_parse(file_path)
    
    def _fallback_parse(self, file_path: str) -> str:
        """
        Резервный парсер через pypdf
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            Простой текст документа
        """
        if not PYPDF_AVAILABLE:
            return "ERROR: No parser available (install markitdown or pypdf)"
        
        try:
            with open(file_path, 'rb') as f:
                pdf_reader = pypdf.PdfReader(f)
                
                pages_text = []
                
                for page_num, page in enumerate(pdf_reader.pages, 1):
                    text = page.extract_text() or ""
                    if text.strip():
                        pages_text.append(f"## Страница {page_num}\n\n{text.strip()}")
                
                return "\n\n".join(pages_text)
                
        except Exception as e:
            self.logger.error(f"Fallback parser failed | error={e}")
            return f"ERROR: Failed to parse PDF: {str(e)}"
    
    def _parse_with_ocr(self, file_path: str) -> str:
        """
        Парсинг PDF через OCR (для отсканированных документов)
        
        Использует Unstructured с поддержкой русского и английского языков
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            Markdown текст с распознанным контентом
        """
        if not UNSTRUCTURED_AVAILABLE:
            self.logger.warning("Unstructured not available, skipping OCR")
            return self._fallback_parse(file_path)
        
        try:
            self.logger.info(f"Starting OCR processing | strategy={self.ocr_strategy}")
            
            # Используем partition_pdf с OCR
            elements = partition_pdf(
                filename=file_path,
                strategy=self.ocr_strategy,
                infer_table_structure=True,
                languages=["rus", "eng"],  # КРИТИЧНО: русский + английский
                extract_images_in_pdf=True,  # Извлекать изображения
                max_partition=None  # Обрабатывать все страницы
            )
            
            if not elements:
                self.logger.warning("OCR returned no elements")
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
            
            self.logger.info(f"OCR processing complete | elements={len(elements)} pages={len(pages_content)} content_length={len(final_markdown)}")
            
            return final_markdown
            
        except Exception as e:
            self.logger.error(f"OCR processing failed | file={file_path} error={type(e).__name__}: {e}")
            return self._fallback_parse(file_path)
