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
from utils.database import PostgreDataBase
from utils.file_manager import File
from tests.runner import run_tests_on_startup

setup_logging()
logger = get_logger("alpaca.worker")

# Инициализация
db = PostgreDataBase(settings.DATABASE_URL)
FILEWATCHER_API = os.getenv("FILEWATCHER_API_URL", "http://localhost:8081")

# Семафоры для ограничения конкурентности разных операций (из settings)
PARSE_SEMAPHORE = Semaphore(settings.WORKER_MAX_CONCURRENT_PARSING)
EMBED_SEMAPHORE = Semaphore(settings.WORKER_MAX_CONCURRENT_EMBEDDING)
LLM_SEMAPHORE = Semaphore(settings.WORKER_MAX_CONCURRENT_LLM)


def process_deleted_file(file: File) -> bool:
    """Обработка deleted файла - удаление чанков и записи
    
    Args:
        file: Объект File с информацией о файле
        
    Returns:
        bool: True если успешно
    """
    try:
        chunks_deleted = db.delete_chunks_by_hash(file.hash)
        db.delete_file_by_hash(file.hash)
        logger.info(f"🪓 Deleted {file.path} and {chunks_deleted} chunks")
        return True
    except Exception as e:
        logger.error(f"Error deleting file {file.path}: {e}")
        return False


def ingest_pipeline(file: File) -> bool:
    """Полный пайплайн обработки файла: парсинг → чанкинг → эмбеддинг
    
    Args:
        file: Объект File с информацией о файле
        
    Returns:
        bool: True если успешно обработан
    """
    logger.info(f"🍎 Start ingest pipeline: {file.path} (hash: {file.hash[:8]}...)")
    
    try:
        # 1. Парсинг (с ограничением конкурентности)
        if file.path.lower().endswith('.docx'):
            logger.info(f"📖 Parsing file: {file.path}")
            with PARSE_SEMAPHORE:
                raw_text = parser_word_old_task({'hash': file.hash, 'path': file.path})
            logger.info(f"✅ Parsed: {len(raw_text) if raw_text else 0} chars")
        else:
            logger.error(f"Unsupported file type: {file.path}")
            db.mark_as_error(file.hash)
            return False

        if not raw_text or not raw_text.strip():
            logger.error(f"Empty parsed text for {file.path}")
            db.mark_as_error(file.hash)
            return False
        
        # 2. Сохранение в temp_parsed
        temp_dir = "/home/alpaca/tmp_md"
        temp_file_path = os.path.join(temp_dir, f"{file.path}.md")
        os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)
        
        with open(temp_file_path, "w", encoding="utf-8") as f:
            f.write(raw_text)
        
        # 3. Чанкинг
        chunks = chunking(file.path, raw_text)
        
        if not chunks:
            logger.warning(f"No chunks created for {file.path}")
            db.mark_as_error(file.hash)
            return False
        
        # 4. Эмбеддинг (с ограничением конкурентности)
        with EMBED_SEMAPHORE:
            chunks_count = embedding(db, file.hash, file.path, chunks)
        
        if chunks_count == 0:
            logger.warning(f"No embeddings created for {file.path}")
            db.mark_as_error(file.hash)
            return False
        
        db.mark_as_ok(file.hash)
        logger.info(f"✅ File processed successfully: {file.path} | chunks={chunks_count}")
        return True
        
    except Exception as e:
        import traceback
        logger.error(f"Pipeline failed for {file.path}: {e}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        db.mark_as_error(file.hash)
        return False


def process_file(file_info: Dict[str, Any]) -> bool:
    """Обработать один файл
    
    Args:
        file_info: Информация о файле из filewatcher
        
    Returns:
        bool: True если успешно обработан
    """
    # Создаём объект File из словаря
    file = File(**file_info)
    
    logger.info(f"Processing file: {file.path} (status={file.status_sync})")
    
    try:
        if file.status_sync == 'deleted':
            # Сначала удаляем чанки, потом обрабатываем как updated если это был updated
            return process_deleted_file(file)
            
        elif file.status_sync == 'updated':
            # Удаляем старые чанки, затем обрабатываем заново
            process_deleted_file(file)
            return ingest_pipeline(file)
            
        elif file.status_sync == 'added':
            # Новый файл - просто обрабатываем
            return ingest_pipeline(file)
            
        else:
            logger.warning(f"Unknown status: {file.status_sync} for {file.path}")
            return False
            
    except Exception as e:
        logger.error(f"✗ Error processing {file.path}: {e}")
        db.mark_as_error(file.hash)
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

