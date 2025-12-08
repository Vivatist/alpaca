"""
Embedder для MCP Server — генерация эмбеддингов через Ollama.
"""

from typing import List
import requests

from logging_config import get_logger

logger = get_logger("mcp_server.embedder")


class OllamaEmbedder:
    """Embedder через Ollama API."""
    
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model
    
    def embed(self, text: str) -> List[float]:
        """Получить embedding для текста."""
        try:
            response = requests.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text},
                timeout=60
            )
            response.raise_for_status()
            return response.json()["embedding"]
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            raise
