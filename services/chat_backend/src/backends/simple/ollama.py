"""
Ollama LLM для Simple Backend.

Потоковая генерация текста через Ollama API.
"""
import json
from typing import Iterator

import httpx

from logging_config import get_logger

logger = get_logger("chat_backend.simple.ollama")


def ollama_stream(
    prompt: str,
    base_url: str,
    model: str,
    system_prompt: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    timeout: float = 300.0
) -> Iterator[str]:
    """
    Потоковая генерация через Ollama API.
    
    Args:
        prompt: Промпт пользователя
        base_url: URL Ollama API
        model: Модель LLM
        system_prompt: Системный промпт
        temperature: Температура генерации
        max_tokens: Максимум токенов
        timeout: Таймаут запроса
        
    Yields:
        Строки текста по мере генерации
    """
    try:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        with httpx.Client(timeout=timeout) as client:
            with client.stream(
                "POST",
                f"{base_url}/api/chat",
                json={
                    "model": model,
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
        
        logger.debug("Ollama stream completed")
        
    except Exception as e:
        logger.error(f"Ollama stream failed: {e}")
