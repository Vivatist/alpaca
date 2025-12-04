"""
Простой экстрактор: только расширение файла.

DEPRECATED: Используйте base_extractor вместо этого.
Оставлен для обратной совместимости.
"""

import os
from typing import Dict, Any

from logging_config import get_logger
from contracts import FileSnapshot

logger = get_logger("ingest.metaextractor.simple")


def simple_extractor(file: FileSnapshot, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Простой экстрактор: только расширение файла.
    
    DEPRECATED: Используйте base_extractor.
    
    Args:
        file: FileSnapshot с информацией о файле
        metadata: Накопленные метаданные от предыдущих экстракторов
        
    Returns:
        Dict с метаданными:
        - extension: расширение файла без точки
    """
    _, ext = os.path.splitext(file.path)
    ext = ext.lower().lstrip('.')
    
    result = metadata.copy()
    result["extension"] = ext
    
    logger.debug(f"Simple extraction | file={file.path} ext={ext}")
    
    return result
