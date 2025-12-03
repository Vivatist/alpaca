"""
Embedders для создания векторных представлений.

Поддерживает:
- ollama: через Ollama API (bge-m3 по умолчанию)

См. HOW_TO_ADD_EMBEDDER.md для инструкции по добавлению нового эмбеддера.
"""

from typing import Dict

from logging_config import get_logger
from contracts import Embedder
from settings import settings

from .ollama import ollama_embedder

logger = get_logger("ingest.embedder")


# Реестр доступных эмбеддеров
EMBEDDERS: Dict[str, Embedder] = {
    "ollama": ollama_embedder,
}


def build_embedder() -> Embedder:
    """Создаёт embedder на основе настроек."""
    backend = getattr(settings, 'EMBEDDER_BACKEND', 'ollama')
    
    if backend not in EMBEDDERS:
        logger.warning(f"Unknown embedder '{backend}', falling back to ollama")
        backend = "ollama"
    
    logger.info(f"Using {backend} embedder | model={settings.OLLAMA_EMBEDDING_MODEL}")
    return EMBEDDERS[backend]


__all__ = [
    "ollama_embedder",
    "EMBEDDERS",
    "build_embedder",
]
