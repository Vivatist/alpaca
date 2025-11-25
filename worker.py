"""
Простой worker для обработки файлов из очереди без Prefect
"""
import os
import time
import requests
import psycopg2
import psycopg2.extras
from typing import Optional, Dict, Any, List

from app.parsers.word.parser_word import parser_word_old_task
from utils.logging import setup_logging, get_logger
from settings import settings
from database import Database

setup_logging()
logger = get_logger("alpaca.worker")

# Инициализация
db = Database(settings.DATABASE_URL)
FILEWATCHER_API = os.getenv("FILEWATCHER_API_URL", "http://localhost:8081")


def get_next_file() -> Optional[Dict[str, Any]]:
    """Получить следующий файл из очереди filewatcher"""
    try:
        response = requests.get(f"{FILEWATCHER_API}/api/next-file", timeout=5)
        if response.status_code == 204:
            return None  # Очередь пуста
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Failed to get next file from filewatcher: {e}")
        return None


def chunking(file_path: str, text: str) -> List[str]:
    """Разбивка текста на чанки
    
    Args:
        file_path: Путь к файлу (для логов)
        text: Распарсенный текст документа
        
    Returns:
        List[str]: список чанков
    """
    try:
        logger.info(f"🔪 Chunking: {file_path}")
        
        chunks = []
        max_chunk_size = 1000  # символов
        paragraphs = text.split('\n\n')
        
        current_chunk = ""
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            if len(current_chunk) + len(para) > max_chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = para
            else:
                current_chunk += "\n\n" + para if current_chunk else para
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        logger.info(f"✅ Created {len(chunks)} chunks for {file_path}")
        return chunks
        
    except Exception as e:
        logger.error(f"Failed to chunk text | file={file_path} error={e}")
        return []


def embedding(file_hash: str, file_path: str, chunks: List[str]) -> int:
    """Создание эмбеддингов через Ollama и сохранение в БД
    
    Args:
        file_hash: Хэш файла
        file_path: Путь к файлу
        chunks: Список текстовых чанков
        
    Returns:
        int: количество успешно сохранённых чанков
    """
    try:
        if not chunks:
            logger.warning(f"No chunks to embed for {file_path}")
            return 0
        
        logger.info(f"🔮 Embedding {len(chunks)} chunks: {file_path}")
        
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
                            'file_hash': file_hash,
                            'file_path': file_path,
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
        
        logger.info(f"✅ Embedded {inserted_count}/{len(chunks)} chunks for {file_path}")
        return inserted_count
        
    except Exception as e:
        logger.error(f"Failed to embed chunks | file={file_path} error={e}")
        return 0


def process_deleted_file(file_hash: str, file_path: str) -> bool:
    """Обработка deleted файла - удаление чанков и записи
    
    Args:
        file_hash: Хэш файла
        file_path: Путь к файлу
        
    Returns:
        bool: True если успешно
    """
    try:
        chunks_deleted = db.delete_chunks_by_hash(file_hash)
        db.delete_file_by_hash(file_hash)
        logger.info(f"🪓 Deleted {file_path} and {chunks_deleted} chunks")
        return True
    except Exception as e:
        logger.error(f"Error deleting file {file_path}: {e}")
        return False


def ingest_pipeline(file_hash: str, file_path: str) -> bool:
    """Полный пайплайн обработки файла: парсинг → чанкинг → эмбеддинг
    
    Args:
        file_hash: Хэш файла
        file_path: Путь к файлу
        
    Returns:
        bool: True если успешно обработан
    """
    logger.info(f"🍎 Start ingest pipeline: {file_path} (hash: {file_hash[:8]}...)")
    db.mark_as_processed(file_hash)
    
    try:
        # 1. Парсинг
        if file_path.lower().endswith('.docx'):
            logger.info(f"📖 Parsing file: {file_path}")
            raw_text = parser_word_old_task({'hash': file_hash, 'path': file_path})
            logger.info(f"✅ Parsed: {len(raw_text) if raw_text else 0} chars")
        else:
            logger.error(f"Unsupported file type: {file_path}")
            db.mark_as_error(file_hash)
            return False

        if not raw_text or not raw_text.strip():
            logger.error(f"Empty parsed text for {file_path}")
            db.mark_as_error(file_hash)
            return False
        
        # 2. Сохранение в temp_parsed
        temp_dir = "/home/alpaca/tmp_md"
        temp_file_path = os.path.join(temp_dir, f"{file_path}.md")
        os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)
        
        with open(temp_file_path, "w", encoding="utf-8") as f:
            f.write(raw_text)
        
        # 3. Чанкинг
        chunks = chunking(file_path, raw_text)
        
        if not chunks:
            logger.warning(f"No chunks created for {file_path}")
            db.mark_as_error(file_hash)
            return False
        
        # 4. Эмбеддинг
        chunks_count = embedding(file_hash, file_path, chunks)
        
        if chunks_count == 0:
            logger.warning(f"No embeddings created for {file_path}")
            db.mark_as_error(file_hash)
            return False
        
        db.mark_as_ok(file_hash)
        logger.info(f"✅ File processed successfully: {file_path} | chunks={chunks_count}")
        return True
        
    except Exception as e:
        import traceback
        logger.error(f"Pipeline failed for {file_path}: {e}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        db.mark_as_error(file_hash)
        return False


def process_file(file_info: Dict[str, Any]) -> bool:
    """Обработать один файл
    
    Args:
        file_info: Информация о файле из filewatcher
        
    Returns:
        bool: True если успешно обработан
    """
    file_path = file_info['file_path']
    file_hash = file_info['file_hash']
    status = file_info['status_sync']
    
    logger.info(f"Processing file: {file_path} (status={status})")
    
    try:
        if status == 'deleted':
            # Сначала удаляем чанки, потом обрабатываем как updated если это был updated
            return process_deleted_file(file_hash, file_path)
            
        elif status == 'updated':
            # Удаляем старые чанки, затем обрабатываем заново
            process_deleted_file(file_hash, file_path)
            return ingest_pipeline(file_hash, file_path)
            
        elif status == 'added':
            # Новый файл - просто обрабатываем
            return ingest_pipeline(file_hash, file_path)
            
        else:
            logger.warning(f"Unknown status: {status} for {file_path}")
            return False
            
    except Exception as e:
        logger.error(f"✗ Error processing {file_path}: {e}")
        db.mark_as_error(file_hash)
        return False


def run_worker(poll_interval: int = 10):
    """Основной цикл worker
    
    Args:
        poll_interval: Интервал опроса очереди в секундах
    """
    logger.info("=" * 60)
    logger.info("Worker started")
    logger.info(f"Filewatcher API: {FILEWATCHER_API}")
    logger.info(f"Poll interval: {poll_interval}s")
    logger.info("=" * 60)
    
    processed_count = 0
    
    while True:
        try:
            # Получаем следующий файл
            file_info = get_next_file()
            
            if file_info is None:
                # Очередь пуста, ждем
                logger.debug("Queue is empty, waiting...")
                time.sleep(poll_interval)
                continue
            
            # Обрабатываем файл
            success = process_file(file_info)
            if success:
                processed_count += 1
                logger.info(f"Total processed: {processed_count}")
            
            # Небольшая пауза между файлами
            time.sleep(1)
            
        except KeyboardInterrupt:
            logger.info("Worker stopped by user")
            break
        except Exception as e:
            logger.error(f"Unexpected error in worker loop: {e}")
            time.sleep(poll_interval)


if __name__ == "__main__":
    run_worker(poll_interval=5)
