"""
Чанкеры для разбиения текста на части.

Поддерживает:
- simple: простое разбиение по размеру
- smart: LangChain RecursiveCharacterTextSplitter с overlap

См. HOW_TO_ADD_CHUNKER.md для инструкции по добавлению нового чанкера.
"""

from typing import Dict

from logging_config import get_logger
from contracts import Chunker
from settings import settings

from .simple import simple_chunker
from .smart import smart_chunker

logger = get_logger("ingest.chunker")


# Реестр доступных чанкеров
CHUNKERS: Dict[str, Chunker] = {
    "simple": simple_chunker,
    "smart": smart_chunker,
}


def build_chunker() -> Chunker:
    """Создаёт чанкер на основе настроек."""
    backend = settings.CHUNKER_BACKEND
    
    if backend not in CHUNKERS:
        logger.warning(f"Unknown chunker '{backend}', falling back to simple")
        backend = "simple"
    
    if backend == "smart":
        logger.info(f"Using smart chunker | size={settings.CHUNK_SIZE} overlap={settings.CHUNK_OVERLAP}")
    else:
        logger.info(f"Using {backend} chunker | size={settings.CHUNK_SIZE}")
    
    return CHUNKERS[backend]


__all__ = [
    "simple_chunker",
    "smart_chunker",
    "CHUNKERS",
    "build_chunker",
]
