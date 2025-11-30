#!/usr/bin/env python3
"""
Encoding Detector - автоопределение кодировки текстовых файлов

Использует chardet для определения кодировки с поддержкой различных кодировок.
"""

from typing import Optional

try:
    import chardet # type: ignore
    CHARDET_AVAILABLE = True
except ImportError:
    CHARDET_AVAILABLE = False

from utils.logging import get_logger

logger = get_logger("alpaca.parser.encoding_detector")


def detect_encoding(file_path: str) -> str:
    """
    Автоопределение кодировки файла
    
    Args:
        file_path: Путь к файлу
        
    Returns:
        Название кодировки (utf-8, windows-1251, etc.)
    """
    if not CHARDET_AVAILABLE:
        logger.warning("chardet not available, using UTF-8 fallback")
        return 'utf-8'
    
    try:
        # Читаем первые 10KB для определения кодировки
        with open(file_path, 'rb') as f:
            raw_data = f.read(10240)  # 10KB достаточно для определения
        
        if not raw_data:
            return 'utf-8'
        
        # Определяем кодировку
        detected = chardet.detect(raw_data)
        encoding = detected.get('encoding', 'utf-8')
        confidence = detected.get('confidence', 0.0)
        
        logger.debug(f"Encoding detection | encoding={encoding} confidence={confidence:.2f}")
        
        # Если уверенность низкая, используем UTF-8
        if confidence < 0.7:
            logger.warning(f"Low confidence in encoding detection | confidence={confidence:.2f} using_utf8=true")
            return 'utf-8'
        
        # Нормализация названий кодировок
        encoding_map = {
            'windows-1251': 'windows-1251',
            'cp1251': 'windows-1251',
            'utf-8': 'utf-8',
            'utf8': 'utf-8',
            'ascii': 'ascii',
            'iso-8859-1': 'latin-1',
            'latin-1': 'latin-1'
        }
        
        normalized = encoding_map.get(encoding.lower(), encoding)
        
        return normalized
        
    except Exception as e:
        logger.warning(f"Encoding detection failed | error={e} using_utf8=true")
        return 'utf-8'
