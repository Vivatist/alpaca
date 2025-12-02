"""
Простой экстрактор метаданных.

Извлекает базовые метаданные из файла:
- extension: расширение файла
"""
import os
from typing import Any, Dict

from utils.logging import get_logger
from core.domain.files.models import FileSnapshot

logger = get_logger("core.metaextractor.simple")


def extract_metadata(file: FileSnapshot) -> Dict[str, Any]:
    """
    Извлекает базовые метаданные из файла.
    
    Args:
        file: FileSnapshot с информацией о файле
        
    Returns:
        Словарь с метаданными:
        - extension: расширение файла (без точки, в нижнем регистре)
    """
    try:
        # Извлекаем расширение
        _, ext = os.path.splitext(file.path)
        extension = ext.lstrip(".").lower() if ext else ""
        
        metadata = {
            "extension": extension,
        }
        
        logger.debug(f"Extracted metadata | file={file.path} metadata={metadata}")
        return metadata
        
    except Exception as e:
        logger.error(f"Failed to extract metadata | file={file.path} error={e}")
        return {"extension": ""}
