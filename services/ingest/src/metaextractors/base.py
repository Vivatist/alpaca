"""
Базовый экстрактор: расширение файла и дата модификации.

Этот экстрактор должен быть первым в цепочке - он устанавливает
базовые метаданные, которые не требуют анализа содержимого.
"""

import os
from datetime import datetime
from typing import Dict, Any

from logging_config import get_logger
from contracts import FileSnapshot

logger = get_logger("ingest.metaextractor.base")


def base_extractor(file: FileSnapshot, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Базовый экстрактор: расширение и дата модификации.
    
    Args:
        file: FileSnapshot с информацией о файле
        metadata: Накопленные метаданные от предыдущих экстракторов
        
    Returns:
        Dict с обновлёнными метаданными:
        - extension: расширение файла без точки
        - modified_at: дата модификации в ISO формате
    """
    _, ext = os.path.splitext(file.path)
    ext = ext.lower().lstrip('.')
    
    result = metadata.copy()
    result["extension"] = ext
    
    # Дата модификации из FileSnapshot или с диска
    if file.mtime:
        modified_at = datetime.fromtimestamp(file.mtime).isoformat()
    else:
        # Fallback: читаем с диска
        try:
            stat = os.stat(file.full_path)
            modified_at = datetime.fromtimestamp(stat.st_mtime).isoformat()
        except OSError:
            modified_at = None
    
    if modified_at:
        result["modified_at"] = modified_at
    
    logger.debug(f"Base extraction | file={file.path} ext={ext} mtime={modified_at}")
    
    return result
