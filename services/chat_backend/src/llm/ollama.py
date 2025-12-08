"""
Ollama LLM — потоковая генерация ответов.
"""
from typing import Iterator
import json
import httpx

from logging_config import get_logger
from settings import settings

logger = get_logger("chat_backend.llm.ollama")


def stream(
    prompt: str,
    system_prompt: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 2048
) -> Iterator[str]:
    """
    Потоковая генерация ответа через Ollama.
    
    Args:
        prompt: Запрос с контекстом
        system_prompt: Системный промпт
        temperature: Температура генерации
        max_tokens: Максимальное количество токенов
        
    Yields:
        Части ответа по мере генерации
    """
    try:
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        with httpx.Client(timeout=300.0) as client:
            with client.stream(
                "POST",
                f"{settings.OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": settings.OLLAMA_LLM_MODEL,
                    "messages": messages,
                    "stream": True,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    }
                }
            ) as response:
                if response.status_code != 200:
                    logger.error(f"Ollama error | status={response.status_code}")
                    return
                
                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            content = data.get("message", {}).get("content", "")
                            if content:
                                yield content
                            if data.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue
        
        logger.debug("LLM stream completed")
        
    except Exception as e:
        logger.error(f"LLM stream failed: {e}")
