"""
MetaExtractors для извлечения метаданных документа.

Поддерживает:
- simple: только расширение файла
- llm: расширение + анализ LLM (title, summary, keywords)

См. HOW_TO_ADD_METAEXTRACTOR.md для инструкции по добавлению нового экстрактора.
"""

import os
from typing import Dict

from logging_config import get_logger
from contracts import MetaExtractor
from settings import settings

from .simple import simple_extractor
from .llm import llm_extractor

logger = get_logger("ingest.metaextractor")


# Реестр доступных экстракторов
EXTRACTORS: Dict[str, MetaExtractor] = {
    "simple": simple_extractor,
    "llm": llm_extractor,
}


def _noop_extractor(file) -> Dict[str, str]:
    """Заглушка: возвращает только расширение."""
    _, ext = os.path.splitext(file.path)
    return {"extension": ext.lower().lstrip('.')}


def build_metaextractor() -> MetaExtractor:
    """Создаёт metaextractor на основе настроек."""
    backend = settings.METAEXTRACTOR_BACKEND
    
    if not settings.ENABLE_METAEXTRACTOR or backend == "none":
        logger.info("MetaExtractor disabled")
        return _noop_extractor
    
    if backend not in EXTRACTORS:
        logger.warning(f"Unknown extractor '{backend}', falling back to simple")
        backend = "simple"
    
    if backend == "llm":
        logger.info(f"Using LLM metaextractor | model={settings.OLLAMA_LLM_MODEL}")
    else:
        logger.info(f"Using {backend} metaextractor")
    
    return EXTRACTORS[backend]


__all__ = [
    "simple_extractor",
    "llm_extractor",
    "EXTRACTORS",
    "build_metaextractor",
]
