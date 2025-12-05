"""
LLM клиенты для генерации ответов.

Поддерживает:
- ollama: через Ollama API (qwen2.5:32b по умолчанию)
"""

from typing import Dict, Callable, Iterator

from logging_config import get_logger
from settings import settings

from .ollama import generate_response as ollama_generate
from .ollama import generate_response_stream as ollama_generate_stream

logger = get_logger("chat_backend.llm")

# Type aliases
LLMGenerator = Callable[[str, str | None, float, int], str]
LLMGeneratorStream = Callable[[str, str | None, float, int], Iterator[str]]

# Реестр LLM backends
LLM_BACKENDS: Dict[str, LLMGenerator] = {
    "ollama": ollama_generate,
}

LLM_STREAM_BACKENDS: Dict[str, LLMGeneratorStream] = {
    "ollama": ollama_generate_stream,
}


def build_llm() -> LLMGenerator:
    """Создаёт LLM клиент на основе настроек."""
    backend = getattr(settings, 'LLM_BACKEND', 'ollama')
    
    if backend not in LLM_BACKENDS:
        logger.warning(f"Unknown LLM backend '{backend}', falling back to ollama")
        backend = "ollama"
    
    logger.info(f"Using {backend} LLM | model={settings.OLLAMA_LLM_MODEL}")
    return LLM_BACKENDS[backend]


# Дефолтный экспорт для обратной совместимости
generate_response = ollama_generate
generate_response_stream = ollama_generate_stream

__all__ = [
    "generate_response",
    "generate_response_stream",
    "build_llm",
    "LLM_BACKENDS",
    "LLM_STREAM_BACKENDS",
]
