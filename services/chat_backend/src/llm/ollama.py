"""
Ollama LLM клиент для генерации ответов.
"""

from typing import Optional, Iterator
import json
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


def generate_response_stream(
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2048
) -> Iterator[str]:
    """
    Потоковая генерация ответа через Ollama LLM.
    
    Args:
        prompt: Запрос пользователя с контекстом
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
                    logger.error(f"Ollama LLM stream error | status={response.status_code}")
                    return
                
                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            content = data.get("message", {}).get("content", "")
                            if content:
                                yield content
                            # Проверяем флаг завершения
                            if data.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue
        
        logger.info("LLM stream completed")
        
    except Exception as e:
        logger.error(f"LLM stream request failed: {e}")
