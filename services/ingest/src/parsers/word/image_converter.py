#!/usr/bin/env python3
"""
Image Converter - утилиты для конвертации изображений

Поддерживает конвертацию WMF/EMF в PNG через ImageMagick или PDF.
"""

import os
import tempfile
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Optional
from PIL import Image
from pdf2image import convert_from_path

from logging_config import get_logger

logger = get_logger("core.parser.image_converter")

# Глобальный lock для LibreOffice (не поддерживает параллельные вызовы)
_libreoffice_lock = threading.Lock()


def convert_wmf_to_png(wmf_path: str, image_idx: int, temp_dir: str) -> Optional[str]:
    """
    Конвертация WMF/EMF изображения в PNG для OCR
    
    WMF (Windows Metafile) не поддерживается PIL напрямую.
    Используем wmf2svg (libwmf-bin) → ImageMagick для конвертации.
    
    Args:
        wmf_path: Путь к WMF файлу
        image_idx: Индекс изображения
        temp_dir: Временная директория
        
    Returns:
        Путь к PNG файлу или None если конвертация не удалась
    """
    png_path = os.path.join(temp_dir, f"image_{image_idx}_converted.png")
    svg_path = os.path.join(temp_dir, f"image_{image_idx}_temp.svg")
    
    # Попытка 1: wmf2svg → ImageMagick (более надёжный для WMF)
    try:
        logger.info(f"Attempting wmf2svg conversion for image {image_idx}")
        
        # Сначала конвертируем WMF → SVG через libwmf
        result_wmf = subprocess.run(
            ['wmf2svg', '-o', svg_path, wmf_path],
            capture_output=True,
            timeout=30,
            text=True
        )
        
        if result_wmf.returncode == 0 and os.path.exists(svg_path):
            # Затем SVG → PNG через ImageMagick
            result_svg = subprocess.run(
                ['convert', svg_path, png_path],
                capture_output=True,
                timeout=30,
                text=True
            )
            
            # Удаляем временный SVG
            if os.path.exists(svg_path):
                os.remove(svg_path)
            
            if result_svg.returncode == 0 and os.path.exists(png_path):
                logger.info(f"WMF converted via wmf2svg: image {image_idx}")
                return png_path
        else:
            logger.debug(f"wmf2svg failed with return code {result_wmf.returncode}")
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception) as e:
        logger.debug(f"wmf2svg conversion exception: {e}")
    
    # Попытка 2: Прямой ImageMagick (может работать для некоторых WMF)
    try:
        logger.debug(f"Trying direct ImageMagick for image {image_idx}")
        result = subprocess.run(
            ['convert', wmf_path, png_path],
            capture_output=True,
            timeout=30,
            text=True
        )
        
        if result.returncode == 0 and os.path.exists(png_path):
            logger.info(f"WMF converted with ImageMagick: image {image_idx}")
            return png_path
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception) as e:
        logger.debug(f"ImageMagick conversion exception: {e}")
    
    try:
        # Попытка 3: Попробовать открыть напрямую через PIL
        # Некоторые "WMF" файлы на самом деле обычные растровые изображения
        img = Image.open(wmf_path)
        img.save(png_path, 'PNG')
        
        logger.info(f"WMF converted with PIL: image {image_idx}")
        return png_path
    except Exception as e:
        logger.warning(f"Failed to convert WMF image {image_idx}: {e}")
        return None


def extract_images_via_pdf(docx_path: str, image_idx: int, temp_dir: str) -> Optional[str]:
    """
    Извлечение изображений через конвертацию DOCX→PDF→PNG
    
    Используется когда WMF/EMF не могут быть конвертированы напрямую.
    
    Args:
        docx_path: Путь к DOCX файлу
        image_idx: Индекс изображения
        temp_dir: Временная директория
        
    Returns:
        Путь к PNG файлу или None если конвертация не удалась
    """
    try:
        # Конвертируем DOCX в PDF через LibreOffice (с lock для предотвращения конфликтов)
        pdf_temp_dir = tempfile.mkdtemp(prefix="alpaca_pdf_convert_")
        
        with _libreoffice_lock:
            result = subprocess.run(
                ['libreoffice', '--headless', '--convert-to', 'pdf', '--outdir', pdf_temp_dir, docx_path],
                capture_output=True,
                text=True,
                timeout=120  # Увеличил таймаут т.к. может быть очередь
            )
        
        if result.returncode != 0:
            logger.error(f"LibreOffice PDF conversion failed | returncode={result.returncode}")
            return None
        
        # Находим созданный PDF
        pdf_files = list(Path(pdf_temp_dir).glob('*.pdf'))
        if not pdf_files:
            logger.error(f"No PDF file created | dir={pdf_temp_dir}")
            return None
        
        pdf_path = str(pdf_files[0])
        logger.info(f"PDF created | path={pdf_path}")
        
        # Конвертируем PDF в изображения
        images = convert_from_path(pdf_path, dpi=200)
        
        if not images:
            logger.error(f"No images extracted from PDF")
            return None
        
        # Сохраняем первую страницу (где обычно находится изображение)
        png_path = os.path.join(temp_dir, f"image_{image_idx}_from_pdf.png")
        images[0].save(png_path, 'PNG')
        
        # Очистка временных файлов
        shutil.rmtree(pdf_temp_dir, ignore_errors=True)
        
        logger.info(f"Image extracted via PDF | path={png_path}")
        return png_path
        
    except Exception as e:
        logger.error(f"PDF extraction failed | error={type(e).__name__}: {e}")
        return None


def get_image_extension(content_type: str) -> str:
    """Определение расширения файла по MIME типу"""
    extensions = {
        'image/jpeg': '.jpg',
        'image/png': '.png',
        'image/gif': '.gif',
        'image/bmp': '.bmp',
        'image/tiff': '.tiff',
        'image/webp': '.webp',
        'image/x-wmf': '.wmf',
        'image/x-emf': '.emf'
    }
    return extensions.get(content_type, '.jpg')
