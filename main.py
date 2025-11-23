"""
ALPACA RAG - Единая точка входа
"""
import os
from typing import Dict, List, Tuple
import warnings

os.environ.setdefault("PYTHONWARNINGS", "ignore::UserWarning")
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic_settings.main")

# Отключаем логирование Prefect ДО импорта
os.environ["PREFECT_LOGGING_LEVEL"] = "WARNING"
os.environ["PREFECT_LOGGING_TO_API_ENABLED"] = "false"

from datetime import timedelta
from prefect import flow, serve, task
from prefect.artifacts import create_table_artifact
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



@task(name="process_deleted_files", retries=2, persist_result=True)
def task_process_deleted_files(
    db: Database,
    files: List[Tuple[str, str, int]]
) -> int:
    """Task: обработка deleted файлов"""
    processed = 0
    
    for file_path, file_hash, file_size in files:
        try:
            logger.info(f"Processing deleted: {file_path}")
            chunks_deleted = db.task_delete_chunks_by_hash(db, file_hash)
            db.task_delete_file(db, file_hash)
            logger.info(f"Deleted {chunks_deleted} chunks and file record")
            processed += 1
        except Exception as e:
            logger.error(f"ERROR when trying to delete a file {file_path}: {e}")
    
    return processed


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
                db.task_call_webhook(webhook_url, file_path, file_hash)
                db.task_mark_as_processed(db, file_hash)
                stats['processed'] += 1
                slots_available -= 1
            except Exception as e:
                logger.error(f"❌ Failed to process added file {file_path}: {e}")
                db.task_mark_as_error(db, file_hash)
        else:
            logger.info(f"⏸️  Workflow limit reached, skipping remaining added files")
            stats['skipped'] = len(files) - stats['processed']
            break
    
    return stats


@task(name="process_updated_files", retries=2, persist_result=True)
def task_process_updated_files(db: Database, webhook_url: str, files: List[Tuple[str, str, int]], slots_available: int) -> Dict[str, int]:
    """Task: обработка updated файлов"""
    stats = {'processed': 0, 'skipped': 0}
    
    for file_path, file_hash, file_size in files:
        if slots_available > 0:
            try:
                logger.info(f"🔄 Processing updated: {file_path}")
                chunks_deleted = db.task_delete_chunks_by_path(db, file_path)
                logger.info(f"🗑️  Deleted {chunks_deleted} old chunks")
                db.task_call_webhook(webhook_url, file_path, file_hash)
                db.task_mark_as_processed(db, file_hash)
                stats['processed'] += 1
                slots_available -= 1
            except Exception as e:
                logger.error(f"❌ Failed to process updated file {file_path}: {e}")
                db.db.task_mark_as_error(db, file_hash)
        else:
            logger.info(f"⏸️  Workflow limit reached, skipping remaining updated files")
            stats['skipped'] = len(files) - stats['processed']
            break
    
    return stats


@flow(name="ingest_files_flow")
def ingest_files_flow():
    """Обработка изменений статусов файлов (added/updated → ingestion, deleted → cleanup)"""
    logger.info("Starting file status processing flow...")
    while True:
        pending_files = db.get_pending_files()
        total_pending = sum(len(files) for files in pending_files.values())
        logger.info(f"📋 Found {total_pending} pending files (deleted:{len(pending_files['deleted'])}, updated:{len(pending_files['updated'])}, added:{len(pending_files['added'])})")
        if total_pending == 0:
            break
        
        if pending_files['deleted']:
            task_process_deleted_files(db, pending_files['deleted'])
        
        if pending_files['updated'] or pending_files['added']:
            logger.info("⏸️  Skipping updated/added files (not implemented yet)")
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
        
        # Не используем setup_handlers() - конфликтует с Prefect Runner
        # atexit уже зарегистрирован, этого достаточно
        
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
