"""
MetaExtractors для извлечения метаданных документа.

Поддерживает:
- simple: только расширение файла
- llm: расширение + анализ LLM (title, summary, keywords)
"""

import os
import json
import re
from typing import Dict, Any
import requests

from logging_config import get_logger
from contracts import FileSnapshot, MetaExtractor
from config import settings

logger = get_logger("ingest.metaextractor")


def simple_extractor(file: FileSnapshot) -> Dict[str, Any]:
    """
    Простой экстрактор: только расширение файла.
    
    Args:
        file: FileSnapshot с информацией о файле
        
    Returns:
        Dict с метаданными
    """
    _, ext = os.path.splitext(file.path)
    ext = ext.lower().lstrip('.')
    
    logger.debug(f"Simple extraction | file={file.path} ext={ext}")
    
    return {
        "extension": ext
    }


def llm_extractor(file: FileSnapshot) -> Dict[str, Any]:
    """
    LLM экстрактор: расширение + анализ содержимого.
    
    Извлекает:
    - extension: расширение файла
    - title: заголовок документа
    - summary: краткое описание
    - keywords: ключевые слова
    
    Args:
        file: FileSnapshot с заполненным raw_text
        
    Returns:
        Dict с метаданными
    """
    # Базовые метаданные
    _, ext = os.path.splitext(file.path)
    ext = ext.lower().lstrip('.')
    
    metadata = {
        "extension": ext
    }
    
    text = file.raw_text or ""
    if not text.strip():
        logger.warning(f"Empty text for LLM extraction | file={file.path}")
        return metadata
    
    # Берём первые N символов для анализа
    preview = text[:settings.LLM_METAEXTRACTOR_PREVIEW_LENGTH] if hasattr(settings, 'LLM_METAEXTRACTOR_PREVIEW_LENGTH') else text[:2000]
    
    prompt = f"""Проанализируй документ и верни JSON с полями:
- title: заголовок или название документа (строка)
- summary: краткое описание содержимого в 1-2 предложениях (строка)
- keywords: до 5 ключевых слов или фраз (массив строк)

Документ:
{preview}

Ответь ТОЛЬКО валидным JSON без пояснений:"""

    try:
        response = requests.post(
            f"{settings.OLLAMA_BASE_URL}/api/generate",
            json={
                "model": settings.OLLAMA_LLM_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 500
                }
            },
            timeout=60
        )
        
        if response.status_code != 200:
            logger.warning(f"LLM request failed | status={response.status_code}")
            return metadata
        
        llm_response = response.json().get('response', '')
        
        # Парсим JSON из ответа
        llm_metadata = _parse_llm_response(llm_response)
        
        if llm_metadata:
            metadata.update(llm_metadata)
            logger.info(f"LLM extraction success | file={file.path} keys={list(llm_metadata.keys())}")
        else:
            logger.warning(f"Failed to parse LLM response | file={file.path}")
        
    except Exception as e:
        logger.warning(f"LLM extraction failed | file={file.path} error={e}")
    
    return metadata


def _parse_llm_response(response: str) -> Dict[str, Any]:
    """Парсинг JSON из ответа LLM."""
    if not response:
        return {}
    
    # Пробуем найти JSON в ответе
    json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group())
            result = {}
            
            if 'title' in data and isinstance(data['title'], str):
                result['title'] = data['title'].strip()
            
            if 'summary' in data and isinstance(data['summary'], str):
                result['summary'] = data['summary'].strip()
            
            if 'keywords' in data and isinstance(data['keywords'], list):
                result['keywords'] = [str(k).strip() for k in data['keywords'] if k]
            
            return result
        except json.JSONDecodeError:
            pass
    
    return {}


def build_metaextractor() -> MetaExtractor:
    """Создаёт metaextractor на основе настроек."""
    backend = settings.METAEXTRACTOR_BACKEND
    
    if not settings.ENABLE_METAEXTRACTOR or backend == "none":
        logger.info("MetaExtractor disabled")
        return lambda f: {"extension": os.path.splitext(f.path)[1].lower().lstrip('.')}
    
    if backend == "llm":
        logger.info(f"Using LLM metaextractor | model={settings.OLLAMA_LLM_MODEL}")
        return llm_extractor
    else:
        logger.info("Using simple metaextractor")
        return simple_extractor


__all__ = [
    "simple_extractor",
    "llm_extractor",
    "build_metaextractor",
]
