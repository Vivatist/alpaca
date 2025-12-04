"""
MetaExtractors для извлечения метаданных документа.

Поддерживает последовательное применение экстракторов через pipeline.
Каждый экстрактор получает накопленные метаданные и добавляет свои.

Доступные экстракторы:
- base: расширение файла + дата модификации
- llm: title, summary, keywords, entities, category (через Ollama)
- simple: только расширение (deprecated, используйте base)

См. HOW_TO_ADD_METAEXTRACTOR.md для инструкции по добавлению нового экстрактора.
"""

import json
from typing import Dict, Any, List, Callable

from logging_config import get_logger
from contracts import FileSnapshot, MetaExtractor
from settings import settings

from .base import base_extractor
from .simple import simple_extractor
from .llm import llm_extractor

logger = get_logger("ingest.metaextractor")


# Тип экстрактора: (file, accumulated_metadata) -> updated_metadata
ExtractorFunc = Callable[[FileSnapshot, Dict[str, Any]], Dict[str, Any]]

# Реестр доступных экстракторов
EXTRACTORS: Dict[str, ExtractorFunc] = {
    "base": base_extractor,
    "simple": simple_extractor,  # deprecated
    "llm": llm_extractor,
}


def get_extractor_pipeline(extractor_names: List[str]) -> MetaExtractor:
    """
    Создаёт pipeline экстракторов для последовательного применения.
    
    Каждый экстрактор получает результат предыдущего и добавляет свои поля.
    
    Args:
        extractor_names: Список имён экстракторов в порядке применения
        
    Returns:
        Функция-экстрактор, применяющая все экстракторы последовательно
    """
    extractors = []
    for name in extractor_names:
        if name in EXTRACTORS:
            extractors.append((name, EXTRACTORS[name]))
        else:
            logger.warning(f"Unknown extractor: {name}, skipping")
    
    if not extractors:
        logger.warning("No valid extractors found, using base only")
        extractors = [("base", base_extractor)]
    
    def pipeline(file: FileSnapshot) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {}
        for name, extractor in extractors:
            try:
                metadata = extractor(file, metadata)
            except Exception as e:
                logger.error(f"Extractor '{name}' failed | file={file.path} error={e}")
        return metadata
    
    names = [name for name, _ in extractors]
    logger.info(f"MetaExtractor pipeline created | extractors={names}")
    return pipeline


def build_metaextractor() -> MetaExtractor:
    """Создаёт metaextractor на основе настроек."""
    if not settings.ENABLE_METAEXTRACTOR:
        logger.info("MetaExtractor disabled")
        # Возвращаем минимальный экстрактор
        return lambda file: base_extractor(file, {})
    
    return get_extractor_pipeline(settings.METAEXTRACTOR_PIPELINE)


__all__ = [
    "base_extractor",
    "simple_extractor",
    "llm_extractor",
    "EXTRACTORS",
    "get_extractor_pipeline",
    "build_metaextractor",
]
