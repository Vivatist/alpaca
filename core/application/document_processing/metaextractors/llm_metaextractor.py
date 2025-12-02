"""
LLM-экстрактор метаданных.

Извлекает метаданные из файла с использованием LLM:
- extension: расширение файла
- title: заголовок документа (извлекается LLM)
- summary: краткое описание (извлекается LLM)
- keywords: ключевые слова (извлекаются LLM)
"""
import json
import os
from typing import Any, Dict, Optional

import requests

from settings import settings
from utils.logging import get_logger
from core.domain.files.models import FileSnapshot

logger = get_logger("core.metaextractor.llm")

# Промпт для извлечения метаданных
METADATA_EXTRACTION_PROMPT = """Проанализируй следующий текст документа и извлеки метаданные.

Текст документа (первые {preview_length} символов):
{text_preview}

Верни JSON со следующими полями:
- title: заголовок или название документа (если есть)
- summary: краткое описание содержимого (1-2 предложения)
- keywords: список из 3-5 ключевых слов/тем документа

Отвечай ТОЛЬКО валидным JSON без markdown-форматирования."""


def _call_llm(prompt: str) -> Optional[str]:
    """
    Вызывает Ollama LLM API.
    
    Args:
        prompt: Промпт для LLM
        
    Returns:
        Ответ LLM или None при ошибке
    """
    try:
        logger.debug(f"Calling LLM | model={settings.OLLAMA_LLM_MODEL}")
        response = requests.post(
            f"{settings.OLLAMA_BASE_URL}/api/generate",
            json={
                "model": settings.OLLAMA_LLM_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,  # Низкая температура для стабильного JSON
                }
            },
            timeout=settings.LLM_METAEXTRACTOR_TIMEOUT,
        )
        response.raise_for_status()
        result = response.json().get("response", "")
        logger.debug(f"LLM response received | length={len(result)}")
        return result
    except requests.exceptions.Timeout:
        logger.error(f"LLM call timeout | timeout={settings.LLM_METAEXTRACTOR_TIMEOUT}s")
        return None
    except Exception as e:
        logger.error(f"LLM call failed | error={e}")
        return None


def _parse_llm_response(response: Optional[str]) -> Dict[str, Any]:
    """
    Парсит ответ LLM и извлекает метаданные.
    
    Args:
        response: Ответ LLM (ожидается JSON)
        
    Returns:
        Словарь с извлечёнными метаданными
    """
    if not response:
        return {}
    
    try:
        import json
        # Пытаемся найти JSON в ответе
        response = response.strip()
        if response.startswith("```"):
            # Убираем markdown code block
            lines = response.split("\n")
            response = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
        
        data = json.loads(response)
        return {
            "title": data.get("title", ""),
            "summary": data.get("summary", ""),
            "keywords": data.get("keywords", []),
        }
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning(f"Failed to parse LLM response | error={e}")
        return {}


def extract_metadata(file: FileSnapshot) -> Dict[str, Any]:
    """
    Извлекает метаданные из файла с использованием LLM.
    
    Args:
        file: FileSnapshot с информацией о файле
        
    Returns:
        Словарь с метаданными:
        - extension: расширение файла
        - title: заголовок (если извлечён LLM)
        - summary: краткое описание (если извлечено LLM)
        - keywords: ключевые слова (если извлечены LLM)
    """
    try:
        # Базовые метаданные (как в simple)
        _, ext = os.path.splitext(file.path)
        extension = ext.lstrip(".").lower() if ext else ""
        
        metadata: Dict[str, Any] = {
            "extension": extension,
        }
        
        # LLM-извлечение (если есть текст)
        if file.raw_text:
            preview_length = settings.LLM_METAEXTRACTOR_PREVIEW_LENGTH
            text_preview = file.raw_text[:preview_length]
            prompt = METADATA_EXTRACTION_PROMPT.format(
                preview_length=preview_length,
                text_preview=text_preview
            )
            
            llm_response = _call_llm(prompt)
            llm_metadata = _parse_llm_response(llm_response)
            metadata.update(llm_metadata)
            
            if llm_metadata:
                logger.info(f"✅ LLM metadata extracted | file={file.path} title={llm_metadata.get('title', '')[:50]}")
        
        logger.debug(f"Extracted metadata | file={file.path} metadata={metadata}")
        return metadata
        
    except Exception as e:
        logger.error(f"Failed to extract metadata | file={file.path} error={e}")
        return {"extension": extension if 'extension' in dir() else ""}
