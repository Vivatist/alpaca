"""
Простой экстрактор: только расширение файла.
"""

import os
from typing import Dict, Any

from logging_config import get_logger
from contracts import FileSnapshot

logger = get_logger("ingest.metaextractor.simple")


def simple_extractor(file: FileSnapshot) -> Dict[str, Any]:
    """
    Простой экстрактор: только расширение файла.
    
    Args:
        file: FileSnapshot с информацией о файле
        
    Returns:
        Dict с метаданными:
        - extension: расширение файла без точки
    """
    _, ext = os.path.splitext(file.path)
    ext = ext.lower().lstrip('.')
    
    logger.debug(f"Simple extraction | file={file.path} ext={ext}")
    
    return {
        "extension": ext
    }
