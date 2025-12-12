"""
Ollama embedder: создание векторных представлений через Ollama API.
"""

from typing import List, Dict, Any
import requests

from logging_config import get_logger
from contracts import FileSnapshot, Repository
from settings import settings

logger = get_logger("ingest.embedder.ollama")

# Размер батча для Ollama API
BATCH_SIZE = 50


def _get_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """
    Получает эмбеддинги для списка текстов одним запросом.
    
    Args:
        texts: Список текстов для эмбеддинга
        
    Returns:
        Список векторов или пустой список при ошибке
    """
    try:
        response = requests.post(
            f"{settings.OLLAMA_BASE_URL}/api/embed",
            json={
                "model": settings.OLLAMA_EMBEDDING_MODEL,
                "input": texts
            },
            timeout=120
        )
        
        if response.status_code != 200:
            logger.error(f"Ollama embedding error | status={response.status_code}")
            return []
        
        embeddings = response.json().get('embeddings', [])
        
        if len(embeddings) != len(texts):
            logger.error(f"Ollama returned {len(embeddings)} embeddings for {len(texts)} texts")
            return []
        
        return embeddings
        
    except Exception as e:
        logger.error(f"Batch embedding request failed: {e}")
        return []


def ollama_embedder(
    repo: Repository,
    file: FileSnapshot,
    chunks: List[str],
    doc_metadata: Dict[str, Any] = None
) -> int:
    """
    Создание эмбеддингов через Ollama и сохранение в БД.
    
    Args:
        repo: Репозиторий для работы с БД
        file: FileSnapshot с информацией о файле
        chunks: Список текстовых чанков
        doc_metadata: Метаданные документа (extension, title, summary, keywords)
        
    Returns:
        Количество успешно сохранённых чанков
    """
    try:
        if not chunks:
            logger.warning(f"No chunks to embed")
            return 0
        
        if doc_metadata is None:
            doc_metadata = {}
        
        logger.info(f"Embedding | chunks={len(chunks)}")
        
        # Удаляем старые чанки
        deleted_count = repo.delete_chunks_by_hash(file.hash)
        if deleted_count > 0:
            logger.info(f"Deleted old chunks | count={deleted_count}")
        
        inserted_count = 0
        total_chunks = len(chunks)
        
        # Обрабатываем чанки батчами
        for batch_start in range(0, total_chunks, BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, total_chunks)
            batch_chunks = chunks[batch_start:batch_end]
            
            # Получаем эмбеддинги для батча
            embeddings = _get_embeddings_batch(batch_chunks)
            
            if not embeddings:
                logger.error(f"Failed to get embeddings for batch {batch_start}-{batch_end}")
                continue
            
            # Сохраняем каждый чанк
            for idx, (chunk_text, embedding) in enumerate(zip(batch_chunks, embeddings)):
                try:
                    global_idx = batch_start + idx
                    # Объединяем метаданные документа с метаданными чанка
                    metadata = {
                        **doc_metadata,
                        'file_hash': file.hash,
                        'file_path': file.path,
                        'chunk_index': global_idx,
                        'total_chunks': total_chunks
                    }
                    
                    repo.save_chunk(chunk_text, metadata, embedding)
                    inserted_count += 1
                    
                except Exception as e:
                    logger.error(f"Error saving chunk {global_idx}: {e}")
                    continue
        
        logger.info(f"Embedded | count={inserted_count}/{total_chunks}")
        return inserted_count
        
    except Exception as e:
        logger.error(f"Embedding failed | error={e}")
        return 0
