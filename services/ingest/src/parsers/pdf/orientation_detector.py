#!/usr/bin/env python3
"""
Быстрый детектор ориентации PDF

Определяет, нужно ли поворачивать документ.
Оптимизирован для скорости - минимум обращений к диску и OCR.
"""

import tempfile
import os
from typing import Tuple, Optional

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    import pytesseract
    from PIL import Image
    from pdf2image import convert_from_path
    TESSERACT_AVAILABLE = True
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    PDF2IMAGE_AVAILABLE = False

from logging_config import get_logger

logger = get_logger("core.parser.orientation_detector")


def quick_check_orientation(file_path: str) -> Tuple[bool, int]:
    """
    БЫСТРАЯ проверка: нужен ли поворот
    
    Стратегия:
    1. Извлекаем текст из первой страницы через PyMuPDF (быстро!)
    2. Считаем русские буквы
    3. Если читаемость > 30% - документ в порядке, поворот НЕ нужен
    4. Если < 30% - нужна детальная проверка
    
    Args:
        file_path: Путь к PDF
        
    Returns:
        (needs_rotation: bool, confidence: int) - нужен ли поворот и уверенность 0-100
    """
    if not PYMUPDF_AVAILABLE:
        return False, 0
    
    try:
        doc = fitz.open(file_path)
        page = doc[0]
        text = page.get_text()
        doc.close()
        
        if not text or len(text) < 50:
            # Мало текста - возможно отсканированный, нужен OCR
            logger.debug(f"Low text content ({len(text)} chars), needs OCR check")
            return False, 0  # Не можем определить быстро
        
        # Подсчёт читаемости: важна доля РУССКИХ букв, не просто латиницы
        alpha = sum(1 for c in text if c.isalpha())
        if alpha == 0:
            return False, 0
        
        russian = sum(1 for c in text if '\u0430' <= c.lower() <= '\u044f' or c in 'ёЁ')
        latin = sum(1 for c in text if 'a' <= c.lower() <= 'z')
        
        # Для русских документов: русские буквы должны преобладать
        # Если много латиницы при малом количестве русских - возможно перевёрнут
        russian_ratio = (russian / alpha) * 100
        latin_ratio = (latin / alpha) * 100
        
        logger.debug(f"Quick check | text={len(text)} alpha={alpha} russian={russian_ratio:.1f}% latin={latin_ratio:.1f}%")
        
        # Логика: для русских документов русские буквы должны быть > 20%
        # Если < 20% русских И есть латиница - вероятно перевёрнут
        if russian_ratio < 20 and latin_ratio > 50:
            # Много латиницы, мало русских = подозрительно
            return True, 80  # НУЖЕН поворот
        elif russian_ratio >= 20:
            # Есть русские буквы = скорее всего OK
            return False, int(russian_ratio)  # НЕ нужен поворот
        else:
            # Мало и русских, и латиницы = неопределённо
            return True, 50  # Проверим через OCR
            
    except Exception as e:
        logger.error(f"Quick check failed | error={e}")
        return False, 0


def detect_best_rotation(file_path: str) -> int:
    """
    Определяет лучший угол поворота через OCR
    
    Тестирует 4 ориентации и выбирает лучшую по количеству русских слов.
    Используется ТОЛЬКО если quick_check показал необходимость поворота.
    
    Args:
        file_path: Путь к PDF
        
    Returns:
        Угол поворота (0, 90, 180, 270)
    """
    if not TESSERACT_AVAILABLE:
        logger.warning("Tesseract not available, cannot detect rotation")
        return 0
    
    try:
        # Конвертируем первую страницу (DPI=200 для баланса скорость/качество)
        logger.debug("Converting PDF to image for rotation detection...")
        images = convert_from_path(file_path, dpi=200, first_page=1, last_page=1)
        
        if not images:
            return 0
        
        img = images[0]
        best_angle = 0
        best_score = 0
        
        # Тестируем все углы
        for angle in [0, 90, 180, 270]:
            rotated = img.rotate(angle, expand=True)
            
            # Сохраняем во временный файл
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                tmp_path = tmp.name
                rotated.save(tmp_path, 'PNG')
            
            try:
                # OCR исключительно с русским языком — так избегаем транслитерации
                text = pytesseract.image_to_string(tmp_path, lang='rus', config='--psm 3')
                
                # Подсчёт русских слов (более надёжная метрика чем буквы)
                words = text.split()
                russian_words = sum(1 for w in words 
                                  if len(w) > 2 and 
                                  any('\u0430' <= c.lower() <= '\u044f' or c in 'ёЁ' for c in w))
                
                # Оценка: приоритет русским словам
                score = russian_words * 3 + len(words)
                
                logger.debug(f"Angle {angle}° | words={len(words)} russian={russian_words} score={score}")
                
                if score > best_score:
                    best_score = score
                    best_angle = angle
                    
            except Exception as e:
                logger.debug(f"OCR failed for angle {angle}° | error={e}")
            finally:
                try:
                    os.remove(tmp_path)
                except:
                    pass
        
        logger.info(f"Best rotation detected | angle={best_angle}° score={best_score}")
        return best_angle
        
    except Exception as e:
        logger.error(f"Rotation detection failed | error={e}")
        return 0


def rotate_pdf_physically(input_path: str, angle: int, output_path: Optional[str] = None) -> Optional[str]:
    """
    Физический поворот PDF через изображения (для сканов)
    
    Args:
        input_path: Исходный PDF
        angle: Угол поворота (90, 180, 270)
        output_path: Путь для сохранения (если None, создаётся временный)
        
    Returns:
        Путь к повёрнутому файлу или None при ошибке
    """
    if not PYMUPDF_AVAILABLE or not PDF2IMAGE_AVAILABLE or angle == 0:
        return input_path
    
    try:
        from pdf2image import convert_from_path
        from PIL import Image
        
        # Конвертируем PDF в изображения
        images = convert_from_path(input_path, dpi=200)
        
        # Поворачиваем изображения
        # PIL использует против часовой стрелки, нам нужно инвертировать
        pil_angle = 360 - angle if angle != 0 else 0
        rotated_images = [img.rotate(pil_angle, expand=True) for img in images]
        
        # Создаём новый PDF
        if output_path is None:
            fd, output_path = tempfile.mkstemp(suffix='.pdf', prefix='rotated_')
            os.close(fd)
        
        # Сохраняем как PDF
        if len(rotated_images) == 1:
            rotated_images[0].save(output_path, 'PDF', resolution=200.0)
        else:
            rotated_images[0].save(
                output_path, 
                'PDF', 
                resolution=200.0,
                save_all=True, 
                append_images=rotated_images[1:]
            )
        
        logger.info(f"PDF rotated {angle}° | pages={len(rotated_images)} output={output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Physical rotation failed | error={e}")
        return None


def smart_rotate_pdf(file_path: str) -> Tuple[str, bool]:
    """
    УМНЫЙ поворот: быстрая проверка → при необходимости детальный анализ → поворот
    
    Оптимизирован для скорости:
    - Большинство документов проходят только quick_check (< 100ms)
    - OCR запускается ТОЛЬКО для перевёрнутых документов
    
    Args:
        file_path: Путь к PDF
        
    Returns:
        (working_path: str, needs_cleanup: bool) - путь к файлу и нужно ли удалить после
    """
    # Шаг 1: Быстрая проверка (< 100ms)
    needs_rotation, confidence = quick_check_orientation(file_path)
    
    if not needs_rotation:
        logger.debug(f"Document orientation OK | confidence={confidence}%")
        return file_path, False
    
    logger.info(f"⚠️ Document may be rotated | confidence={confidence}%, running OCR detection...")
    
    # Шаг 2: Детальный анализ через OCR (медленно, но только для перевёрнутых)
    best_angle = detect_best_rotation(file_path)
    
    if best_angle == 0:
        logger.info("No rotation needed after OCR check")
        return file_path, False
    
    # Шаг 3: Физический поворот
    rotated_path = rotate_pdf_physically(file_path, best_angle)
    
    if rotated_path and rotated_path != file_path:
        return rotated_path, True  # Нужен cleanup
    else:
        return file_path, False
