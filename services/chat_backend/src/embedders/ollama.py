"""
Ollama embedder: создание векторных представлений через Ollama API.

Используется для получения embedding'а запроса пользователя
для поиска релевантных чанков в pgvector.
"""

from typing import List
import httpx

from logging_config import get_logger
from settings import settings

logger = get_logger("chat_backend.embedder.ollama")


def ollama_embedder(text: str) -> List[float]:
    """
    Создание эмбеддинга для одного текста через Ollama.
    
    Args:
        text: Текст для эмбеддинга (обычно запрос пользователя)
        
    Returns:
        Вектор размерности 1024 (для bge-m3) или пустой список при ошибке
    """
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{settings.OLLAMA_BASE_URL}/api/embed",
                json={
                    "model": settings.OLLAMA_EMBEDDING_MODEL,
                    "input": [text]
                }
            )
            
            if response.status_code != 200:
                logger.error(f"Ollama embedding error | status={response.status_code}")
                return []
            
            embeddings = response.json().get('embeddings', [])
            
            if not embeddings:
                logger.error("Ollama returned empty embeddings")
                return []
            
            return embeddings[0]
        
    except Exception as e:
        logger.error(f"Embedding request failed: {e}")
        return []
