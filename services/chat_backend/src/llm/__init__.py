"""
LLM клиенты для генерации ответов.

Поддерживает:
- ollama: через Ollama API (qwen2.5:32b по умолчанию)
- langchain_agent: агентский RAG через LangChain (экспериментальный)

Переключение через ENV:
- LLM_BACKEND=ollama (по умолчанию)
- LLM_BACKEND=langchain_agent
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


def _get_langchain_generators():
    """Ленивая загрузка LangChain генераторов."""
    try:
        from .langchain_agent import generate_response, generate_response_stream
        return generate_response, generate_response_stream
    except ImportError:
        logger.warning("LangChain agent not available (missing dependencies)")
        return None, None


# Реестр LLM backends
LLM_BACKENDS: Dict[str, LLMGenerator] = {
    "ollama": ollama_generate,
}

LLM_STREAM_BACKENDS: Dict[str, LLMGeneratorStream] = {
    "ollama": ollama_generate_stream,
}


def _register_langchain_if_available():
    """Регистрирует LangChain backend если доступен."""
    gen, gen_stream = _get_langchain_generators()
    if gen and gen_stream:
        LLM_BACKENDS["langchain_agent"] = gen
        LLM_STREAM_BACKENDS["langchain_agent"] = gen_stream
        logger.debug("LangChain agent backend registered")


# Пробуем зарегистрировать LangChain при импорте
_register_langchain_if_available()


def get_backend_name() -> str:
    """Возвращает имя текущего backend из настроек."""
    return getattr(settings, 'LLM_BACKEND', 'ollama')


def build_llm() -> LLMGenerator:
    """Создаёт LLM клиент на основе настроек."""
    backend = get_backend_name()
    
    if backend not in LLM_BACKENDS:
        logger.warning(f"Unknown LLM backend '{backend}', falling back to ollama")
        backend = "ollama"
    
    logger.info(f"Using {backend} LLM | model={settings.OLLAMA_LLM_MODEL}")
    return LLM_BACKENDS[backend]


def build_llm_stream() -> LLMGeneratorStream:
    """Создаёт streaming LLM клиент на основе настроек."""
    backend = get_backend_name()
    
    if backend not in LLM_STREAM_BACKENDS:
        logger.warning(f"Unknown LLM backend '{backend}', falling back to ollama")
        backend = "ollama"
    
    return LLM_STREAM_BACKENDS[backend]


# Динамический выбор на основе настроек
def generate_response(
    prompt: str,
    system_prompt: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 2048
) -> str:
    """Генерация ответа через выбранный backend."""
    generator = build_llm()
    return generator(prompt, system_prompt, temperature, max_tokens)


def generate_response_stream(
    prompt: str,
    system_prompt: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 2048
) -> Iterator[str]:
    """Потоковая генерация ответа через выбранный backend."""
    generator = build_llm_stream()
    return generator(prompt, system_prompt, temperature, max_tokens)


__all__ = [
    "generate_response",
    "generate_response_stream",
    "build_llm",
    "build_llm_stream",
    "get_backend_name",
    "LLM_BACKENDS",
    "LLM_STREAM_BACKENDS",
]
