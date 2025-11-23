"""
ALPACA RAG - Единая точка входа
"""
import os
from time import sleep
from typing import Dict, List, Tuple
import warnings

os.environ.setdefault("PYTHONWARNINGS", "ignore::UserWarning")
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic_settings.main")

# Отключаем логирование Prefect ДО импорта
os.environ["PREFECT_LOGGING_LEVEL"] = "WARNING"
os.environ["PREFECT_LOGGING_TO_API_ENABLED"] = "false"

from datetime import timedelta
from prefect import flow, serve, task
from pydantic import BaseModel


class FileID(BaseModel):
    """Идентификатор файла (hash + path)"""
    hash: str
    path: str
    
    class Config:
        frozen = True
        
        
from utils.logging import setup_logging, get_logger
from utils.process_lock import ProcessLock
from app.file_watcher import FileWatcherService
from settings import settings
from database import Database

# Настраиваем логирование в каждом процессе
setup_logging()
logger = get_logger("alpaca.main")

# Сервисы
file_watcher = FileWatcherService(
    database_url=settings.DATABASE_URL,
    monitored_path=settings.MONITORED_PATH,
    allowed_extensions=settings.ALLOWED_EXTENSIONS.split(','),
    file_min_size=settings.FILE_MIN_SIZE,
    file_max_size=settings.FILE_MAX_SIZE,
    excluded_dirs=settings.EXCLUDED_DIRS.split(','),
    excluded_patterns=settings.EXCLUDED_PATTERNS.split(',')
)

db = Database(settings.DATABASE_URL)


@flow(name="file_watcher_flow")
def file_watcher_flow():
    """Сканирование и синхронизация файлов"""
    result = file_watcher.scan_and_sync()
    
    return result


@task(name="process_deleted_file", retries=2, persist_result=True)
def task_process_deleted_file(
    db: Database, file_id: FileID) -> FileID:
    """Task: обработка deleted файла"""
    try:
        chunks_deleted = db.delete_chunks_by_hash(file_id.hash)
        db.delete_file_by_hash(file_id.hash)
        logger.info(f"Deleted {file_id.path} and {chunks_deleted} chunks")
    except Exception as e:
        logger.error(f"ERROR when trying to delete a file {file_id.path}: {e}")
        return None
    return file_id


@flow(name="parsing_flow")
def parsing_flow(file_id: dict) -> str:
    """Flow: парсинг документа в текст"""
    file_id = FileID(**file_id)
    
    try:
        logger.info(f"📖 Processing parsing: {file_id.path}")
        # parsed_text = parser_service.parse(file_id.path)    
        sleep(3)  # Симуляция времени парсинга 2-5 сек
        return "--text--"  # TODO: вернуть реальный текст
    except Exception as e:
        logger.error(f"Failed to process parsing file {file_id.path}: {e}")
        db.mark_as_error(file_id.hash)
        return ""


@flow(name="ingest_pipeline")
def ingest_pipeline(file_id: dict) -> str:
    """Входная точка пайплайна нового документа"""    
    file_id = FileID(**file_id)  # Преобразуем dict обратно в FileID
    logger.info(f"🍎 Start ingest pipeline: {file_id.path} (hash: {file_id.hash[:8]}...)")
    db.mark_as_processed(file_id.hash)
    
    # 1. Парсим файл в сырой текст
    raw_text = parsing_flow(file_id.model_dump())
    
    # TODO: Реализовать пайплайн. пока только парсим и сохраняем в файл
    temp_dir = os.path.join(os.path.dirname(__file__), "temp_parsed")
    temp_file_path = os.path.join(temp_dir, f"{file_id.path}.txt")
    
    # Создаём все родительские директории
    os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)
    
    with open(temp_file_path, "w", encoding="utf-8") as f:
        f.write(raw_text)
    
    db.mark_as_ok(file_id.hash)
    logger.info(f"✅ File processed successfully: {file_id.path}")
    return ""


@flow(name="process_pending_files_flow")
def process_pending_files_flow():
    """Обработка изменений статусов файлов (added/updated → ingestion, deleted → cleanup)"""
    pending_files = db.get_pending_files()
    total_pending = sum(len(files) for files in pending_files.values())
    logger.info(f"📋 Found {total_pending} pending files (deleted:{len(pending_files['deleted'])}, updated:{len(pending_files['updated'])}, added:{len(pending_files['added'])})")

    # Цикл обработки файлов до тех пор, пока есть отмеченные как deleted pending-файлы
    for file_id in pending_files['deleted']:
        task_process_deleted_file(db, file_id)

    # Цикл обработки файлов до тех пор, пока есть отмеченные как updated pending-файлы
    for file_id in pending_files['updated']:
        task_process_deleted_file(db, file_id)
        ingest_pipeline(file_id.model_dump())

    # Цикл обработки файлов до тех пор, пока есть отмеченные как added pending-файлы
    for file_id in pending_files['added']:
        ingest_pipeline(file_id.model_dump())

    return
        
        
if __name__ == "__main__":
    # Защита от дублирования процессов (как HTTP сервер проверяет порт)
    process_lock = ProcessLock('/tmp/alpaca_rag.pid')
    process_lock.acquire()
    # process_lock.setup_handlers()  # Отключено: конфликт с Prefect Runner SIGTERM
    
    try:
        logger.info("Starting ALPACA RAG system...")
        
        # Сброс статусов processed у файлов в базе при старте
        reset_count = file_watcher.reset_processed_statuses()
            
        # Запуск нескольких flows с ограничением параллелизма
        serve(
            file_watcher_flow.to_deployment(
            name="file-watcher",
            interval=timedelta(seconds=settings.SCAN_MONITORED_FOLDER_INTERVAL),
            description="Сканирование и синхронизация файлов",
            concurrency_limit=1
            ),
            process_pending_files_flow.to_deployment(
            name="process_pending_files_flow",
            interval=timedelta(seconds=settings.PROCESS_FILE_CHANGES_INTERVAL),
            description="Обработка изменений статусов файлов",
            concurrency_limit=settings.MAX_HEAVY_WORKFLOWS
            )
        )
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
    finally:
        process_lock.release()
