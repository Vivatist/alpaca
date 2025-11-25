"""
Worker - бизнес-логика обработки файлов
Содержит функции парсинга, чанкинга, эмбеддинга и обработки файлов
"""
import os
from typing import Dict, Any
from threading import Semaphore

from app.parsers.word.parser_word import parser_word_old_task
from app.chunkers.custom_chunker import chunking
from app.embedders.custom_embedder import embedding
from utils.logging import setup_logging, get_logger
from utils.worker import Worker
from settings import settings
from utils.database import PostgreDatabase
from tests.runner import run_tests_on_startup

setup_logging()
logger = get_logger("alpaca.worker")

# Инициализация
db = PostgreDatabase(settings.DATABASE_URL)
FILEWATCHER_API = os.getenv("FILEWATCHER_API_URL", "http://localhost:8081")

# Семафоры для ограничения конкурентности разных операций (из settings)
PARSE_SEMAPHORE = Semaphore(settings.WORKER_MAX_CONCURRENT_PARSING)
EMBED_SEMAPHORE = Semaphore(settings.WORKER_MAX_CONCURRENT_EMBEDDING)
LLM_SEMAPHORE = Semaphore(settings.WORKER_MAX_CONCURRENT_LLM)


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
    
    try:
        # 1. Парсинг (с ограничением конкурентности)
        if file_path.lower().endswith('.docx'):
            logger.info(f"📖 Parsing file: {file_path}")
            with PARSE_SEMAPHORE:
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
        
        # 4. Эмбеддинг (с ограничением конкурентности)
        with EMBED_SEMAPHORE:
            chunks_count = embedding(db, file_hash, file_path, chunks)
        
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

if __name__ == "__main__":
    # Запуск тестов при старте (если включено в настройках)
    tests_passed = run_tests_on_startup(settings)

    if not tests_passed:
        exit(1)

    # Создаём worker и запускаем
    worker = Worker(
        database_url=settings.DATABASE_URL,
        filewatcher_api_url=FILEWATCHER_API,
        process_file_func=process_file # передаем функцию которую будем дергать при изменении на диске
    )
    worker.start(poll_interval=settings.WORKER_POLL_INTERVAL, max_workers=settings.WORKER_MAX_CONCURRENT_FILES)

