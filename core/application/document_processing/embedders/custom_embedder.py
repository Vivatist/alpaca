from typing import List
import requests

from core.domain.files.repository import FileRepository
from core.domain.files.models import FileSnapshot
from utils.logging import get_logger
from settings import settings

logger = get_logger("core.embedder")


def custom_embedding(repo: FileRepository, file: FileSnapshot, chunks: List[str]) -> int:
    """Создание эмбеддингов через Ollama и сохранение в БД
    
    Args:
        repo: Репозиторий для работы с БД
        file: Объект FileSnapshot с информацией о файле
        chunks: Список текстовых чанков
        
    Returns:
        int: количество успешно сохранённых чанков
    """
    try:
        if not chunks:
            logger.warning(f"No chunks to embed for {file.path}")
            return 0
        
        logger.info(f"🔮 Embedding {len(chunks)} chunks: {file.path}")
        
        # Удаляем старые чанки через репозиторий
        deleted_count = repo.delete_chunks_by_hash(file.hash)
        if deleted_count > 0:
            logger.info(f"🗑️ Deleted {deleted_count} old chunks for {file.path}")
        
        inserted_count = 0
        
        for idx, chunk_text in enumerate(chunks):
            try:
                response = requests.post(
                    f"{settings.OLLAMA_BASE_URL}/api/embeddings",
                    json={
                        "model": settings.OLLAMA_EMBEDDING_MODEL,
                        "prompt": chunk_text
                    },
                    timeout=60
                )
                
                if response.status_code != 200:
                    logger.error(f"Ollama embedding error | status={response.status_code}")
                    continue
                
                embedding = response.json().get('embedding')
                
                if not embedding:
                    logger.error(f"No embedding in response for chunk {idx}")
                    continue
                
                metadata = {
                    'file_hash': file.hash,
                    'file_path': file.path,
                    'chunk_index': idx,
                    'total_chunks': len(chunks)
                }
                
                # Сохраняем через репозиторий
                repo.save_chunk(chunk_text, metadata, embedding)
                inserted_count += 1
                
            except Exception as e:
                logger.error(f"Error embedding chunk {idx}: {e}")
                continue
        
        logger.info(f"✅ Embedded {inserted_count}/{len(chunks)} chunks for {file.path}")
        return inserted_count
        
    except Exception as e:
        logger.error(f"Failed to embed chunks | file={file.path} error={e}")
        return 0
