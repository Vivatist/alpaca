#!/usr/bin/env python3
"""
PDF Rotator - автоматическое исправление ориентации PDF

Детектирует неправильную ориентацию страниц и исправляет их перед парсингом.
Использует Tesseract OSD и OpenCV для точного определения ориентации.
"""

import os
import re
import tempfile
from typing import Optional, Tuple

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False

try:
    import cv2
    import numpy as np
    from deskew import determine_skew
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False

try:
    from pdf2image import convert_from_path
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False

from utils.logging import get_logger

logger = get_logger("alpaca.parser.pdf_rotator")


def detect_text_orientation(page) -> int:
    """
    Определяет правильную ориентацию страницы по тексту
    
    Метод: извлекаем текст и считаем читаемые слова.
    Правильная ориентация = больше читаемого текста.
    
    Args:
        page: PyMuPDF page object
        
    Returns:
        Угол поворота для исправления (0, 90, 180, 270)
    """
    if not PYMUPDF_AVAILABLE:
        return 0
    
    # Тестируем все возможные повороты
    rotations = [0, 90, 180, 270]
    best_rotation = 0
    max_readable_score = 0
    
    for rotation in rotations:
        # Временно применяем поворот
        original_rotation = page.rotation
        page.set_rotation(rotation)
        
        # Извлекаем текст
        text = page.get_text()
        
        # Считаем "читаемость" - количество кириллических/латинских букв
        readable_chars = sum(1 for c in text if c.isalpha() or c.isspace())
        vertical_chars = sum(1 for c in text if c in '|│║╔╗╚╝')  # Вертикальные символы
        
        # Оценка: больше букв - лучше, меньше вертикальных символов - лучше
        score = readable_chars - (vertical_chars * 2)
        
        logger.debug(f"Rotation {rotation}° | readable={readable_chars} vertical={vertical_chars} score={score}")
        
        if score > max_readable_score:
            max_readable_score = score
            best_rotation = rotation
        
        # Восстанавливаем исходный поворот
        page.set_rotation(original_rotation)
    
    return best_rotation


def fix_pdf_orientation(input_path: str, output_path: Optional[str] = None) -> Optional[str]:
    """
    Автоматически исправляет ориентацию всех страниц PDF
    
    Args:
        input_path: Путь к исходному PDF
        output_path: Путь для сохранения исправленного PDF (если None, создаётся временный файл)
        
    Returns:
        Путь к исправленному файлу или None при ошибке
    """
    if not PYMUPDF_AVAILABLE:
        logger.warning("PyMuPDF не установлен, пропуск исправления ориентации")
        return input_path
    
    try:
        doc = fitz.open(input_path)
        needs_rotation = False
        rotations_applied = []
        
        # Проверяем каждую страницу
        for i, page in enumerate(doc):
            current_rotation = page.rotation
            optimal_rotation = detect_text_orientation(page)
            
            if optimal_rotation != current_rotation:
                page.set_rotation(optimal_rotation)
                needs_rotation = True
                rotations_applied.append(f"Page {i+1}: {current_rotation}° → {optimal_rotation}°")
                logger.info(f"📐 Поворот страницы {i+1} | from={current_rotation}° to={optimal_rotation}°")
        
        if not needs_rotation:
            logger.info("✅ Ориентация корректна, поворот не требуется")
            doc.close()
            return input_path
        
        # Сохраняем исправленный PDF
        if output_path is None:
            # Создаём временный файл
            fd, output_path = tempfile.mkstemp(suffix='.pdf', prefix='rotated_')
            os.close(fd)
        
        doc.save(output_path, garbage=4, deflate=True)
        doc.close()
        
        logger.info(f"✅ PDF исправлен | rotations={len(rotations_applied)} output={output_path}")
        for rotation_info in rotations_applied:
            logger.debug(rotation_info)
        
        return output_path
        
    except Exception as e:
        logger.error(f"❌ Ошибка исправления ориентации | file={input_path} error={e}")
        return None


def detect_orientation_with_tesseract(image_path: str) -> Tuple[int, float]:
    """
    Определяет ориентацию изображения через Tesseract OSD
    
    Args:
        image_path: Путь к изображению
        
    Returns:
        (угол поворота, уверенность)
    """
    if not PYTESSERACT_AVAILABLE:
        return 0, 0.0
    
    try:
        # Tesseract OSD (Orientation and Script Detection) с поддержкой русского языка
        osd = pytesseract.image_to_osd(image_path, config='--psm 0 -l rus')
        
        # Парсим результат
        angle = int(re.search(r'Rotate: (\d+)', osd).group(1))
        confidence = float(re.search(r'Orientation confidence: ([\d.]+)', osd).group(1))
        
        logger.debug(f"Tesseract OSD | angle={angle}° confidence={confidence}")
        return angle, confidence
        
    except Exception as e:
        logger.debug(f"Tesseract OSD failed | error={e}")
        return 0, 0.0


def detect_skew_with_opencv(image_path: str) -> float:
    """
    Определяет угол наклона (skew) изображения через OpenCV
    
    Args:
        image_path: Путь к изображению
        
    Returns:
        Угол наклона в градусах
    """
    if not OPENCV_AVAILABLE:
        return 0.0
    
    try:
        # Читаем изображение
        image = cv2.imread(image_path)
        if image is None:
            return 0.0
        
        # Конвертируем в grayscale
        grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Определяем угол наклона
        angle = determine_skew(grayscale)
        
        logger.debug(f"OpenCV deskew | angle={angle:.2f}°")
        return angle
        
    except Exception as e:
        logger.debug(f"OpenCV deskew failed | error={e}")
        return 0.0


def deskew_image(image_path: str, output_path: str, angle: Optional[float] = None) -> bool:
    """
    Исправляет наклон изображения
    
    Args:
        image_path: Путь к исходному изображению
        output_path: Путь для сохранения
        angle: Угол поворота (если None, определяется автоматически)
        
    Returns:
        True если успешно
    """
    if not OPENCV_AVAILABLE:
        return False
    
    try:
        # Читаем изображение
        image = cv2.imread(image_path)
        if image is None:
            return False
        
        # Определяем угол если не указан
        if angle is None:
            grayscale = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            angle = determine_skew(grayscale)
        
        # Поворачиваем изображение
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(
            image, M, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE
        )
        
        # Сохраняем
        cv2.imwrite(output_path, rotated)
        logger.debug(f"Image deskewed | angle={angle:.2f}° output={output_path}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Deskew failed | error={e}")
        return False


def fix_pdf_orientation_advanced(input_path: str, output_path: Optional[str] = None, use_ocr: bool = True) -> Optional[str]:
    """
    Улучшенное исправление ориентации PDF с использованием Tesseract OSD и OpenCV
    
    Args:
        input_path: Путь к исходному PDF
        output_path: Путь для сохранения (если None, создаётся временный файл)
        use_ocr: Использовать Tesseract OSD для определения ориентации
        
    Returns:
        Путь к исправленному файлу или None при ошибке
    """
    if not PDF2IMAGE_AVAILABLE or not PYMUPDF_AVAILABLE:
        logger.warning("pdf2image или PyMuPDF не установлены")
        return fix_pdf_orientation(input_path, output_path)
    
    try:
        # Конвертируем PDF в изображения для анализа (высокое DPI для лучшего OCR)
        images = convert_from_path(input_path, dpi=300, first_page=1, last_page=1)
        
        if not images:
            logger.warning("Не удалось конвертировать PDF в изображения")
            return fix_pdf_orientation(input_path, output_path)
        
        # Сохраняем первую страницу во временный файл
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_img:
            tmp_img_path = tmp_img.name
            images[0].save(tmp_img_path, 'PNG')
        
        # Определяем ориентацию через Tesseract OSD
        rotation_angle = 0
        confidence = 0.0
        
        if use_ocr and PYTESSERACT_AVAILABLE:
            rotation_angle, confidence = detect_orientation_with_tesseract(tmp_img_path)
            logger.info(f"📐 Tesseract OSD | angle={rotation_angle}° confidence={confidence:.2f}")
            
            # Если OSD не уверен (низкая confidence), пробуем вручную проверить все углы
            if confidence < 1.5:
                logger.info("⚠️ Низкая уверенность OSD, проверяем все углы вручную...")
                best_angle = 0
                best_score = 0
                
                # Пробуем все возможные повороты
                from PIL import Image
                img = Image.open(tmp_img_path)
                
                for angle in [0, 90, 180, 270]:
                    # PIL.rotate: положительный угол = против часовой стрелки
                    # Для исправления ориентации нужен поворот по часовой стрелке
                    rotated = img.rotate(angle, expand=True)
                    
                    # Сохраняем временно
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_rot:
                        tmp_rot_path = tmp_rot.name
                        rotated.save(tmp_rot_path, 'PNG')
                    
                    try:
                        # Пробуем OCR с русским языком
                        text = pytesseract.image_to_string(tmp_rot_path, lang='rus', config='--psm 3')
                        
                        # Считаем "читаемость" - приоритет русским словам
                        words = text.split()
                        readable_words = [w for w in words if len(w) > 2 and any(c.isalpha() for c in w)]
                        russian_words = sum(1 for w in readable_words if any('а' <= c.lower() <= 'я' or c in 'ёЁ' for c in w))
                        
                        # Оценка: русские слова * 3 + общее количество слов
                        score = russian_words * 3 + len(readable_words)
                        
                        logger.debug(f"Angle {angle}° | words={len(readable_words)} russian={russian_words} score={score} | sample: {text[:50]}")
                        
                        if score > best_score:
                            best_score = score
                            best_angle = angle
                    except:
                        pass
                    finally:
                        try:
                            os.remove(tmp_rot_path)
                        except:
                            pass
                
                if best_score > 5:  # Минимум 5 читаемых слов
                    rotation_angle = best_angle
                    confidence = best_score / 10.0  # Искусственная confidence
                    logger.info(f"✅ Ручная проверка | best_angle={best_angle}° score={best_score}")
        
        # Определяем наклон через OpenCV
        skew_angle = 0.0
        if OPENCV_AVAILABLE:
            skew_angle = detect_skew_with_opencv(tmp_img_path)
            logger.info(f"📐 OpenCV skew | angle={skew_angle:.2f}°")
        
        # Удаляем временное изображение
        try:
            os.remove(tmp_img_path)
        except:
            pass
        
        # Применяем поворот к PDF если нужно
        if rotation_angle == 0 and abs(skew_angle) < 1.0:
            logger.info("✅ Ориентация и наклон корректны")
            return input_path
        
        # Открываем PDF для исправления (физический поворот)
        if rotation_angle != 0:
            logger.info(f"🔄 Применяю физический поворот {rotation_angle}° ко всем страницам...")
            
            # Создаём новый PDF с повёрнутыми страницами
            doc_in = fitz.open(input_path)
            doc_out = fitz.open()  # Новый пустой документ
            
            for page_num in range(len(doc_in)):
                page = doc_in[page_num]
                
                # Создаём матрицу поворота
                if rotation_angle == 90:
                    mat = fitz.Matrix(0, 1, -1, 0, page.mediabox.width, 0)
                elif rotation_angle == 180:
                    mat = fitz.Matrix(-1, 0, 0, -1, page.mediabox.width, page.mediabox.height)
                elif rotation_angle == 270:
                    mat = fitz.Matrix(0, -1, 1, 0, 0, page.mediabox.height)
                else:
                    mat = fitz.Matrix(1, 0, 0, 1, 0, 0)  # Нет поворота
                
                # Определяем новый размер страницы после поворота
                if rotation_angle in [90, 270]:
                    new_width = page.mediabox.height
                    new_height = page.mediabox.width
                else:
                    new_width = page.mediabox.width
                    new_height = page.mediabox.height
                
                # Создаём новую страницу в выходном документе
                new_page = doc_out.new_page(width=new_width, height=new_height)
                
                # Копируем содержимое с применением поворота
                new_page.show_pdf_page(new_page.rect, doc_in, page_num, rotate=rotation_angle)
            
            doc_in.close()
            logger.info(f"✅ Физический поворот {rotation_angle}° применён к {len(doc_out)} страницам")
        
            # Сохраняем исправленный PDF
            if output_path is None:
                fd, output_path = tempfile.mkstemp(suffix='.pdf', prefix='rotated_')
                os.close(fd)
            
            doc_out.save(output_path, garbage=4, deflate=True)
            doc_out.close()
        else:
            # Только skew, без поворота - используем оригинал
            return input_path
        
        logger.info(f"✅ PDF исправлен | rotation={rotation_angle}° skew={skew_angle:.2f}° output={output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"❌ Ошибка улучшенного исправления ориентации | file={input_path} error={e}")
        # Fallback на простой метод
        return fix_pdf_orientation(input_path, output_path)


def auto_rotate_before_parsing(file_path: str, use_advanced: bool = True) -> Tuple[str, bool]:
    """
    Wrapper для парсеров: автоматически исправляет ориентацию если нужно
    
    Args:
        file_path: Путь к PDF файлу
        use_advanced: Использовать улучшенный метод (Tesseract OSD + OpenCV)
        
    Returns:
        (путь к файлу для парсинга, нужно ли удалить временный файл)
    """
    if not PYMUPDF_AVAILABLE:
        return file_path, False
    
    try:
        # Используем улучшенный метод если доступен
        if use_advanced and PDF2IMAGE_AVAILABLE:
            rotated_path = fix_pdf_orientation_advanced(file_path)
        else:
            rotated_path = fix_pdf_orientation(file_path)
        
        if rotated_path and rotated_path != file_path:
            # Был создан временный файл с исправленной ориентацией
            return rotated_path, True
        else:
            # Ориентация корректна или исправление не удалось
            return file_path, False
            
    except Exception as e:
        logger.error(f"❌ Ошибка auto_rotate | file={file_path} error={e}")
        return file_path, False
