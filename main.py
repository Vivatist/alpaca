"""
Worker - бизнес-логика обработки файлов
Содержит функции парсинга, чанкинга, эмбеддинга и обработки файлов
"""
import os
from typing import Dict, Any
from threading import Semaphore

from app.parsers.word_parser_module.word_parser import WordParser
from app.chunkers.custom_chunker import chunking
from app.embedders.custom_embedder import embedding
from utils.logging import setup_logging, get_logger
from utils.worker import Worker
from settings import settings
from utils.database import PostgreDataBase
from utils.file_manager import File, FileManager
from tests.runner import run_tests_on_startup

logger = get_logger("alpaca.worker")

# Инициализация
db = PostgreDataBase(settings.DATABASE_URL)
fm = FileManager(db)
word_parser = WordParser(enable_ocr=True)  # Создаём экземпляр парсера
FILEWATCHER_API = os.getenv("FILEWATCHER_API_URL", "http://localhost:8081")

# Семафоры для ограничения конкурентности разных операций (из settings)
PARSE_SEMAPHORE = Semaphore(settings.WORKER_MAX_CONCURRENT_PARSING)
EMBED_SEMAPHORE = Semaphore(settings.WORKER_MAX_CONCURRENT_EMBEDDING)
LLM_SEMAPHORE = Semaphore(settings.WORKER_MAX_CONCURRENT_LLM)


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
                file.raw_text = word_parser.parse(file)
            logger.info(f"✅ Parsed: {len(file.raw_text) if file.raw_text else 0} chars")
        else:
            logger.error(f"Unsupported file type: {file.path}")
            fm.mark_as_error(file)
            return False

        if not file.raw_text or not file.raw_text.strip():
            logger.error(f"Empty parsed text for {file.path}")
            fm.mark_as_error(file)
            return False
    
        
        # 2. Сохранение в temp_parsed
        fm.save_file_to_disk(file)
        
        # 3. Чанкинг
        chunks = chunking(file)
        
        if not chunks:
            logger.warning(f"No chunks created for {file.path}")
            fm.mark_as_error(file)
            return False
        
        # 4. Эмбеддинг (с ограничением конкурентности)
        with EMBED_SEMAPHORE:
            chunks_count = embedding(db, file, chunks)
        
        if chunks_count == 0:
            logger.warning(f"No embeddings created for {file.path}")
            fm.mark_as_error(file)
            return False
        
        fm.mark_as_ok(file)
        logger.info(f"✅ File processed successfully: {file.path} | chunks={chunks_count}")
        return True
        
    except Exception as e:
        import traceback
        logger.error(f"Pipeline failed for {file.path}: {e}")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        fm.mark_as_error(file)
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
            # Удаляем чанки и файл из БД
            fm.delete_file_and_chunks(file)
            return True
            
        elif file.status_sync == 'updated':
            # Удаляем только старые чанки, файл остаётся в БД
            fm.delete_chunks_only(file)
            return ingest_pipeline(file)
            
        elif file.status_sync == 'added':
            # Новый файл - просто обрабатываем
            return ingest_pipeline(file)
            
        else:
            logger.warning(f"Unknown status: {file.status_sync} for {file.path}")
            return False
            
    except Exception as e:
        logger.error(f"✗ Error processing {file.path}: {e}")
        fm.mark_as_error(file)
        return False

if __name__ == "__main__":
    # Запуск тестов при старте (если включено в настройках)
    tests_passed = run_tests_on_startup(settings)

    if not tests_passed:
        exit(1)

    # Переинициализируем logging после тестов (pytest может закрыть handlers)
    setup_logging()
    logger.info("🚀 Запуск worker после успешного прохождения тестов")

    # Создаём worker и запускаем
    worker = Worker(
        db = db,
        filewatcher_api_url=FILEWATCHER_API,
        process_file_func=process_file # передаем функцию которую будем дергать при изменении на диске
    )
    worker.start(poll_interval=settings.WORKER_POLL_INTERVAL, max_workers=settings.WORKER_MAX_CONCURRENT_FILES)

