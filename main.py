"""
ALPACA RAG - Единая точка входа
"""
import os
from dataclasses import dataclass
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


@dataclass(frozen=True)
class FileID:
    """Идентификатор файла (hash + path)"""
    hash: str
    path: str
from utils.logging import setup_logging, get_logger
from utils.process_lock import ProcessLock
from app.file_watcher import FileWatcherService
from app.flows.file_status_processor import FileStatusProcessorService
from settings import settings
from database import Database

# Настраиваем логирование в каждом процессе
setup_logging()
logger = get_logger(__name__)

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

# file_processor = FileStatusProcessorService(
#     database_url=settings.DATABASE_URL,
#     webhook_url=settings.N8N_WEBHOOK_URL,
#     max_heavy_workflows=settings.MAX_HEAVY_WORKFLOWS
# )

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

@task(name="process_added_files", retries=2, persist_result=True)
def task_process_added_files(
    db: Database,
    webhook_url: str,
    files: List[Tuple[str, str, int]],
    slots_available: int
) -> Dict[str, int]:
    """Task: обработка added файлов"""
    stats = {'processed': 0, 'skipped': 0}
    
    for file_path, file_hash, file_size in files:
        if slots_available > 0:
            try:
                logger.info(f"➕ Processing added: {file_path}")
                db.call_webhook(webhook_url, file_path, file_hash)
                db.mark_as_processed(file_hash)
                stats['processed'] += 1
                slots_available -= 1
            except Exception as e:
                logger.error(f"❌ Failed to process added file {file_path}: {e}")
                db.mark_as_error(file_hash)
        else:
            logger.info(f"⏸️  Workflow limit reached, skipping remaining added files")
            stats['skipped'] = len(files) - stats['processed']
            break
    
    return stats


@task(name="process_updated_files", retries=2, persist_result=True)
def task_process_updated_files(
    db: Database, file_path, file_hash: str) -> bool:   
    """Task: обработка updated файлов"""

    
    for file_path, file_hash, file_size in files:
        if slots_available > 0:
            try:
                logger.info(f"🔄 Processing updated: {file_path}")
                chunks_deleted = db.delete_chunks_by_path(file_path)
                logger.info(f"🗑️  Deleted {chunks_deleted} old chunks")
                db.call_webhook(webhook_url, file_path, file_hash)
                db.mark_as_processed(file_hash)
                stats['processed'] += 1
                slots_available -= 1
            except Exception as e:
                logger.error(f"❌ Failed to process updated file {file_path}: {e}")
                db.mark_as_error(file_hash)
        else:
            logger.info(f"⏸️  Workflow limit reached, skipping remaining updated files")
            stats['skipped'] = len(files) - stats['processed']
            break
    
    return stats


@flow(name="parsing_flow")
def parsing_flow(file_id: FileID) -> str:
    """Парсинг документа в текст
    
    Args:
        file_id: Идентификатор файла (hash + path)
    
    Returns:
        str: Извлечённый текст документа
    """
    logger.info(f"🔍 Parsing file: {file_id.path} (hash: {file_id.hash[:8]}...)")
    
    # TODO: Реализовать вызов парсера
    # parsed_text = parser_service.parse(file_id.path)    
    sleep(2 + os.urandom(1)[0] / 255 * 3)  # Симуляция времени парсинга 2-5 сек
    return ""


@flow(name="ingest_files_flow")
def ingest_files_flow():
    """Обработка изменений статусов файлов (added/updated → ingestion, deleted → cleanup)"""
    pending_files = db.get_pending_files()
    total_pending = sum(len(files) for files in pending_files.values())
    logger.info(f"📋 Found {total_pending} pending files (deleted:{len(pending_files['deleted'])}, updated:{len(pending_files['updated'])}, added:{len(pending_files['added'])})")

    # Цикл обработки файлов до тех пор, пока есть отмеченные как deleted pending-файлы
    for file_id in pending_files['deleted']:
        task_process_deleted_file(db, file_id)
        
    # Цикл обработки файлов до тех пор, пока есть отмеченные как deleted pending-файлы
    for file_id in pending_files['updated']:
        task_process_deleted_file(db, file_id)
        
        
        
        if pending_files['updated'] or pending_files['added']:
            task_process_updated_files(
                db,
                settings.N8N_WEBHOOK_URL,
                pending_files['updated'],
                settings.MAX_HEAVY_WORKFLOWS
            )
            break  # Временно прерываем цикл, чтобы не зависнуть
    result = pending_files
    return result
        
        
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
            ingest_files_flow.to_deployment(
                name="ingest_files_flow",
                interval=timedelta(seconds=settings.PROCESS_FILE_CHANGES_INTERVAL),
                description="Обработка изменений статусов файлов",
                concurrency_limit=1
            )
        )
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
    finally:
        process_lock.release()
