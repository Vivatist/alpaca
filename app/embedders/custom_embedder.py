from typing import List
import requests
import psycopg2
import psycopg2.extras

from utils.database.database import Database
from utils.logging import get_logger
from settings import settings
from utils.file_manager import File

logger = get_logger("alpaca.embedder")


def embedding(db: Database, file: File, chunks: List[str]) -> int:
    """Создание эмбеддингов через Ollama и сохранение в БД
    
    Args:
        db: Экземпляр Database для работы с БД
        file: Объект File с информацией о файле
        chunks: Список текстовых чанков
        
    Returns:
        int: количество успешно сохранённых чанков
    """
    try:
        if not chunks:
            logger.warning(f"No chunks to embed for {file.path}")
            return 0
        
        logger.info(f"🔮 Embedding {len(chunks)} chunks: {file.path}")
        
        with db.get_connection() as conn:
            with conn.cursor() as cur:
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
                        
                        embedding_str = '[' + ','.join(map(str, embedding)) + ']'
                        
                        metadata = {
                            'file_hash': file.hash,
                            'file_path': file.path,
                            'chunk_index': idx,
                            'total_chunks': len(chunks)
                        }
                        
                        cur.execute("""
                            INSERT INTO chunks (content, metadata, embedding)
                            VALUES (%s, %s, %s::vector)
                        """, (chunk_text, psycopg2.extras.Json(metadata), embedding_str))
                        
                        inserted_count += 1
                        
                    except Exception as e:
                        logger.error(f"Error embedding chunk {idx}: {e}")
                        continue
                
                conn.commit()
        
        logger.info(f"✅ Embedded {inserted_count}/{len(chunks)} chunks for {file.path}")
        return inserted_count
        
    except Exception as e:
        logger.error(f"Failed to embed chunks | file={file.path} error={e}")
        return 0
