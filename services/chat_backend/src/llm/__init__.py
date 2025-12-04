"""
Ollama LLM клиент для генерации ответов.
"""

from typing import List, Dict, Any, Optional
import httpx

from logging_config import get_logger
from settings import settings

logger = get_logger("chat_backend.llm.ollama")


def generate_response(
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2048
) -> str:
    """
    Генерация ответа через Ollama LLM.
    
    Args:
        prompt: Запрос пользователя с контекстом
        system_prompt: Системный промпт
        temperature: Температура генерации
        max_tokens: Максимальное количество токенов
        
    Returns:
        Сгенерированный ответ или пустая строка при ошибке
    """
    try:
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        with httpx.Client(timeout=300.0) as client:
            response = client.post(
                f"{settings.OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": settings.OLLAMA_LLM_MODEL,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    }
                }
            )
            
            if response.status_code != 200:
                logger.error(f"Ollama LLM error | status={response.status_code}")
                return ""
            
            result = response.json()
            answer = result.get("message", {}).get("content", "")
            
            logger.info(f"LLM response generated | tokens={len(answer.split())}")
            return answer
        
    except Exception as e:
        logger.error(f"LLM request failed: {e}")
        return ""


# Реестр LLM backends (для будущего расширения)
LLM_BACKENDS = {
    "ollama": generate_response,
}


def build_llm():
    """Создаёт LLM клиент на основе настроек."""
    backend = getattr(settings, 'LLM_BACKEND', 'ollama')
    
    if backend not in LLM_BACKENDS:
        logger.warning(f"Unknown LLM backend '{backend}', falling back to ollama")
        backend = "ollama"
    
    logger.info(f"Using {backend} LLM | model={settings.OLLAMA_LLM_MODEL}")
    return LLM_BACKENDS[backend]


__all__ = [
    "generate_response",
    "build_llm",
]
