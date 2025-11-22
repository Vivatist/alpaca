"""
Генерация embeddings через Ollama API
"""

from typing import List
import httpx
import logging
import asyncio

from settings import settings

logger = logging.getLogger(__name__)


class Embedder:
    """Генерация векторных представлений текста через Ollama"""
    
    def __init__(
        self,
        ollama_url: str = None,
        model: str = None,
        timeout: int = None
    ):
        self.ollama_url = ollama_url or settings.OLLAMA_BASE_URL
        self.model = model or settings.OLLAMA_EMBED_MODEL
        self.timeout = timeout or settings.OLLAMA_TIMEOUT
    
    async def generate_embedding(self, text: str) -> List[float]:
        """
        Генерирует embedding для одного текста
        
        Args:
            text: Текст для векторизации
        
        Returns:
            Вектор embedding или пустой список при ошибке
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/embeddings",
                    json={
                        "model": self.model,
                        "prompt": text
                    }
                )
                
                if response.status_code != 200:
                    logger.error(
                        f"Ollama API error: {response.status_code} - {response.text}"
                    )
                    return []
                
                result = response.json()
                embedding = result.get('embedding', [])
                
                if not embedding:
                    logger.error(f"Empty embedding returned for text: {text[:50]}...")
                    return []
                
                return embedding
        
        except httpx.TimeoutException:
            logger.error(f"Timeout while generating embedding for text: {text[:50]}...")
            return []
        except Exception as e:
            logger.error(f"Error generating embedding: {e}", exc_info=True)
            return []
    
    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Генерирует embeddings для списка текстов
        
        Args:
            texts: Список текстов
        
        Returns:
            Список векторов embeddings
        """
        if not texts:
            return []
        
        logger.info(f"Generating embeddings for {len(texts)} texts using {self.model}")
        
        # Генерируем embeddings параллельно
        tasks = [self.generate_embedding(text) for text in texts]
        embeddings = await asyncio.gather(*tasks)
        
        # Фильтруем пустые результаты
        valid_embeddings = [emb for emb in embeddings if emb]
        
        logger.info(
            f"Generated {len(valid_embeddings)}/{len(texts)} embeddings successfully"
        )
        
        return valid_embeddings
    
    async def generate_embeddings_batch(
        self,
        texts: List[str],
        batch_size: int = 10
    ) -> List[List[float]]:
        """
        Генерирует embeddings батчами для экономии ресурсов
        
        Args:
            texts: Список текстов
            batch_size: Размер батча
        
        Returns:
            Список векторов embeddings
        """
        if not texts:
            return []
        
        logger.info(
            f"Generating embeddings for {len(texts)} texts "
            f"in batches of {batch_size}"
        )
        
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            logger.debug(f"Processing batch {i//batch_size + 1}/{(len(texts)-1)//batch_size + 1}")
            
            batch_embeddings = await self.generate_embeddings(batch)
            all_embeddings.extend(batch_embeddings)
            
            # Небольшая пауза между батчами чтобы не перегрузить Ollama
            if i + batch_size < len(texts):
                await asyncio.sleep(0.1)
        
        return all_embeddings


async def generate_embeddings(texts: List[str], batch_size: int = 10) -> List[List[float]]:
    """
    Удобная функция для генерации embeddings
    
    Args:
        texts: Список текстов
        batch_size: Размер батча для обработки
    
    Returns:
        Список векторов embeddings
    """
    embedder = Embedder()
    return await embedder.generate_embeddings_batch(texts, batch_size)


async def generate_embedding(text: str) -> List[float]:
    """
    Удобная функция для генерации одного embedding
    
    Args:
        text: Текст
    
    Returns:
        Вектор embedding
    """
    embedder = Embedder()
    return await embedder.generate_embedding(text)
