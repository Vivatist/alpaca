"""
Ollama Embedder для Simple Backend.

Генерирует эмбеддинги через локальный Ollama API.
"""
from typing import List, Callable

import httpx

from logging_config import get_logger

logger = get_logger("chat_backend.simple.embedder")


def ollama_embedder(
    base_url: str,
    model: str = "bge-m3:latest",
    timeout: float = 60.0
) -> Callable[[str], List[float]]:
    """
    Фабрика для создания embedder-функции через Ollama.
    
    Args:
        base_url: URL Ollama API (например, http://ollama:11434)
        model: Модель для эмбеддингов (например, bge-m3:latest)
        timeout: Таймаут запроса в секундах
        
    Returns:
        Функция (text: str) -> List[float]
    """
    
    def embed(text: str) -> List[float]:
        """Генерирует эмбеддинг для текста."""
        if not text or not text.strip():
            logger.warning("Empty text for embedding")
            return []
        
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    f"{base_url}/api/embed",
                    json={"model": model, "input": text}
                )
                response.raise_for_status()
                data = response.json()
                
                # Ollama возвращает {"embeddings": [[...], ...]}
                embeddings = data.get("embeddings", [])
                if embeddings and len(embeddings) > 0:
                    return embeddings[0]
                
                logger.warning(f"Empty embedding response: {data}")
                return []
                
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            return []
    
    return embed


def build_embedder(base_url: str, model: str) -> Callable[[str], List[float]]:
    """
    Построить embedder из настроек.
    
    Args:
        base_url: URL Ollama API
        model: Модель для эмбеддингов
    """
    logger.info(f"✅ Embedder: ollama | model={model}")
    return ollama_embedder(base_url=base_url, model=model)
