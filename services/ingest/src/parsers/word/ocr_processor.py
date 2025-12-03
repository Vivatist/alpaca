#!/usr/bin/env python3
"""
OCR Processor - обработка изображений с OCR

Извлекает изображения из Word документов и выполняет OCR через Unstructured API.
"""

import os
import tempfile
import requests
from typing import List, Dict, Optional
from docx import Document  # type: ignore

from utils.logging import get_logger
from .image_converter import convert_wmf_to_png, extract_images_via_pdf, get_image_extension
from settings import settings

logger = get_logger("core.parser.ocr_processor")


def extract_images_from_docx(file_path: str) -> List[Dict]:
    """
    Извлечение изображений из Word документа для OCR
    
    Args:
        file_path: Путь к DOCX файлу
        
    Returns:
        List[Dict] с информацией об изображениях (index, path, size, type)
    """
    images = []
    
    try:
        doc = Document(file_path)
        temp_dir = tempfile.mkdtemp(prefix="alpaca_word_images_")
        
        logger.info(f"Checking for images in document | file={file_path} temp_dir={temp_dir}")
        
        image_idx = 0
        for rel in doc.part.rels.values():
            if "image" in rel.target_ref:
                image_idx += 1
                
                try:
                    image_data = rel.target_part.blob
                    
                    if not image_data:
                        logger.warning(f"Empty image data | index={image_idx}")
                        continue
                    
                    # Определяем расширение по content_type
                    content_type = rel.target_part.content_type
                    ext = get_image_extension(content_type)
                    
                    # Сохраняем во временную директорию
                    image_path = os.path.join(temp_dir, f"image_{image_idx}{ext}")
                    with open(image_path, 'wb') as f:
                        f.write(image_data)
                    
                    # Проверяем что файл создан
                    if not os.path.exists(image_path):
                        logger.error(f"Failed to save image | index={image_idx} path={image_path}")
                        continue
                    
                    logger.debug(f"Image saved | index={image_idx} size={len(image_data)} type={content_type}")
                    
                    # КРИТИЧНО: Конвертируем WMF/EMF в PNG для OCR
                    if content_type in ('image/x-wmf', 'image/x-emf') or ext in ('.wmf', '.emf'):
                        converted_path = convert_wmf_to_png(image_path, image_idx, temp_dir)
                        if converted_path:
                            image_path = converted_path
                            ext = '.png'
                            logger.info(f"Converted WMF/EMF to PNG | index={image_idx} path={converted_path}")
                        else:
                            logger.warning(f"WMF/EMF conversion failed, trying PDF method | index={image_idx}")
                            # Альтернатива: конвертируем весь DOCX в PDF, затем в изображения
                            pdf_converted = extract_images_via_pdf(file_path, image_idx, temp_dir)
                            if pdf_converted:
                                image_path = pdf_converted
                                ext = '.png'
                                logger.info(f"Converted via PDF method | index={image_idx} path={pdf_converted}")
                            else:
                                logger.error(f"All conversion methods failed | index={image_idx}")
                                continue
                    
                    images.append({
                        'index': image_idx,
                        'path': image_path,
                        'size': len(image_data),
                        'type': content_type
                    })
                    
                except Exception as e:
                    logger.error(f"Failed to extract image | index={image_idx} error={type(e).__name__}: {e}")
        
        logger.info(f"Extracted {len(images)} images for OCR (file={file_path})")
        
    except Exception as e:
        logger.warning(f"Error extracting images (file={file_path}): {e}")
    
    return images


def process_images_with_ocr(images: List[Dict], ocr_strategy: str = "auto") -> List[str]:
    """
    OCR обработка изображений через Unstructured API (HTTP)
    
    Args:
        images: List изображений с путями
        ocr_strategy: Стратегия OCR ('auto', 'hi_res', 'fast')
        
    Returns:
        List OCR текстов для каждого изображения (в том же порядке)
    """
    if not images:
        logger.info("No images to process with OCR")
        return []
    
    ocr_texts = []
    successful = 0
    failed = 0
    
    logger.info(f"Starting OCR for {len(images)} images | strategy={ocr_strategy}")
    
    for img in images:
        try:
            # Проверка существования файла
            if not os.path.exists(img['path']):
                logger.error(f"Image file not found | index={img['index']} path={img['path']}")
                ocr_texts.append("")  # Пустой текст для этого изображения
                failed += 1
                continue
            
            # Проверка размера файла
            file_size = os.path.getsize(img['path'])
            if file_size == 0:
                logger.error(f"Image file is empty | index={img['index']} path={img['path']}")
                ocr_texts.append("")
                failed += 1
                continue
            
            logger.info(f"Processing image with OCR | index={img['index']} type={img['type']} size={file_size} path={img['path']}")
            
            # Вызов Unstructured API через HTTP
            with open(img['path'], 'rb') as f:
                response = requests.post(
                    settings.UNSTRUCTURED_API_URL,
                    files={'files': (os.path.basename(img['path']), f)},
                    data=[
                        ('strategy', ocr_strategy if ocr_strategy != 'auto' else 'hi_res'),
                        ('languages', 'rus'),
                        ('languages', 'eng'),
                    ],
                    timeout=120
                )
            
            if response.status_code != 200:
                logger.error(f"Unstructured API error | index={img['index']} status={response.status_code}")
                ocr_texts.append("")
                failed += 1
                continue
            
            elements = response.json()
            
            if not elements:
                logger.warning(f"No OCR elements extracted | index={img['index']}")
                ocr_texts.append("")
                failed += 1
                continue
            
            # Извлекаем текст из элементов
            image_text = "\n\n".join([
                el.get('text', '') for el in elements 
                if el.get('text', '').strip()
            ])
            
            if image_text.strip():
                ocr_texts.append(image_text)
                successful += 1
                logger.info(f"OCR completed | index={img['index']} text_length={len(image_text)}")
            else:
                logger.warning(f"OCR produced empty text | index={img['index']}")
                ocr_texts.append("")
                failed += 1
            
        except Exception as e:
            logger.error(f"OCR failed | index={img['index']} error={type(e).__name__}: {e}")
            ocr_texts.append("")
            failed += 1
        
        finally:
            # Всегда удаляем временный файл
            try:
                if os.path.exists(img['path']):
                    os.remove(img['path'])
                    logger.debug(f"Cleaned up temp image | path={img['path']}")
            except Exception as e:
                logger.warning(f"Failed to remove temp image | path={img['path']} error={e}")
    
    logger.info(f"OCR processing complete | total={len(images)} successful={successful} failed={failed}")
    
    return ocr_texts
