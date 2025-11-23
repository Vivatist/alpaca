"""
ALPACA RAG - Единая точка входа
"""
import os
import warnings

os.environ.setdefault("PYTHONWARNINGS", "ignore::UserWarning")
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic_settings.main")

# Отключаем логирование Prefect ДО импорта
os.environ["PREFECT_LOGGING_LEVEL"] = "WARNING"
os.environ["PREFECT_LOGGING_TO_API_ENABLED"] = "false"

from datetime import timedelta
from typing import Dict, List, Tuple
from prefect import flow, serve, task
from prefect.artifacts import create_table_artifact
from app.utils.logging import setup_logging, get_logger
from app.utils.process_lock import ProcessLock
from app.file_watcher import FileWatcherService
from app.flows.file_status_processor import FileStatusProcessorService
from settings import settings
import time

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

file_processor = FileStatusProcessorService(
    database_url=settings.DATABASE_URL,
    webhook_url=settings.N8N_WEBHOOK_URL,
    max_heavy_workflows=settings.MAX_HEAVY_WORKFLOWS
)


# === FILE WATCHER TASKS ===

@task(name="scan_disk", retries=3, persist_result=True)
def task_scan_disk() -> list:
    """Task: сканирование диска"""
    return file_watcher.scan()


@task(name="sync_files_to_db", retries=3, persist_result=True)
def task_sync_files(files: list) -> dict:
    """Task: синхронизация файлов с БД по хешам"""
    return file_watcher.sync_by_hash(files)


@task(name="sync_vector_status", retries=3, persist_result=True)
def task_sync_status() -> dict:
    """Task: синхронизация статусов с векторной БД"""
    return file_watcher.sync_status()


@task(name="reset_processed_statuses", persist_result=True)
def task_reset_processed() -> int:
    """Task: сброс статусов 'processed' на 'ok'"""
    return file_watcher.reset_processed_statuses()


@flow(name="file_watcher_flow")
def file_watcher_flow():
    """Сканирование и синхронизация файлов"""
    start_time = time.time()
    
    try:
        # Каждый шаг - отдельная task с retry и мониторингом
        files = task_scan_disk()
        file_sync = task_sync_files(files)
        status_sync = task_sync_status()
        
        duration = time.time() - start_time
        logger.info(
            f"disc[total:{len(files)}, "
            f"+{file_sync['added']}, "
            f"~{file_sync['updated']}, "
            f"-{file_sync['deleted']}]  "
            f"base[ok:{status_sync['ok']}, "
            f"a:{status_sync['added']}, "
            f"u:{status_sync['updated']}] "
            f"in {duration:.2f}s"
        )
        
        # Создаём артефакт с результатами сканирования
        create_table_artifact(
            key="scan-summary",
            table=[
                {"Metric": "Files on disk", "Value": len(files)},
                {"Metric": "Added", "Value": file_sync['added']},
                {"Metric": "Updated", "Value": file_sync['updated']},
                {"Metric": "Deleted", "Value": file_sync['deleted']},
                {"Metric": "Unchanged", "Value": file_sync['unchanged']},
                {"Metric": "Status OK", "Value": status_sync['ok']},
                {"Metric": "Status Added", "Value": status_sync['added']},
                {"Metric": "Status Updated", "Value": status_sync['updated']},
                {"Metric": "Duration (s)", "Value": f"{duration:.2f}"},
            ],
            description="File Watcher Scan Summary"
        )
        
        return {
            'success': True,
            'disk_files': len(files),
            'file_sync': file_sync,
            'status_sync': status_sync,
            'duration': duration
        }
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"❌ Scan failed after {duration:.2f}s: {e}", exc_info=True)
        raise


# === FILE STATUS PROCESSOR TASKS ===

@task(name="get_pending_files", retries=2, persist_result=True)
def task_get_pending_files() -> Dict[str, List[Tuple]]:
    """Task: получение файлов требующих обработки"""
    return file_processor.get_pending_files()


@task(name="get_processed_count", retries=2, persist_result=True)
def task_get_processed_count() -> int:
    """Task: получение количества файлов в обработке"""
    return file_processor.get_processed_count()


@task(name="call_ingestion_webhook", retries=3, persist_result=True)
def task_call_webhook(file_path: str, file_hash: str) -> bool:
    """Task: вызов webhook для ingestion"""
    return file_processor.call_webhook(file_path, file_hash)


@task(name="delete_chunks_by_path", retries=2, persist_result=True)
def task_delete_chunks_by_path(file_path: str) -> int:
    """Task: удаление chunks по пути"""
    return file_processor.delete_chunks_by_path(file_path)


@task(name="delete_chunks_by_hash", retries=2, persist_result=True)
def task_delete_chunks_by_hash(file_hash: str) -> int:
    """Task: удаление chunks по хэшу"""
    return file_processor.delete_chunks_by_hash(file_hash)


@task(name="mark_as_processed", persist_result=True)
def task_mark_as_processed(file_hash: str) -> bool:
    """Task: пометка файла как processed"""
    return file_processor.mark_as_processed(file_hash)


@task(name="mark_as_error", persist_result=True)
def task_mark_as_error(file_hash: str) -> bool:
    """Task: пометка файла как error"""
    return file_processor.mark_as_error(file_hash)


@task(name="delete_file_by_hash", persist_result=True)
def task_delete_file(file_hash: str) -> bool:
    """Task: удаление записи файла"""
    return file_processor.delete_file(file_hash)


@task(name="process_added_files", retries=2, persist_result=True)
def task_process_added_files(files: List[Tuple[str, str, int]], slots_available: int) -> Dict[str, int]:
    """Task: обработка added файлов"""
    stats = {'processed': 0, 'skipped': 0}
    
    for file_path, file_hash, file_size in files:
        if slots_available > 0:
            try:
                logger.info(f"➕ Processing added: {file_path}")
                task_call_webhook(file_path, file_hash)
                task_mark_as_processed(file_hash)
                stats['processed'] += 1
                slots_available -= 1
            except Exception as e:
                logger.error(f"❌ Failed to process added file {file_path}: {e}")
                task_mark_as_error(file_hash)
        else:
            logger.info(f"⏸️  Workflow limit reached, skipping remaining added files")
            stats['skipped'] = len(files) - stats['processed']
            break
    
    return stats


@task(name="process_updated_files", retries=2, persist_result=True)
def task_process_updated_files(files: List[Tuple[str, str, int]], slots_available: int) -> Dict[str, int]:
    """Task: обработка updated файлов"""
    stats = {'processed': 0, 'skipped': 0}
    
    for file_path, file_hash, file_size in files:
        if slots_available > 0:
            try:
                logger.info(f"🔄 Processing updated: {file_path}")
                chunks_deleted = task_delete_chunks_by_path(file_path)
                logger.info(f"🗑️  Deleted {chunks_deleted} old chunks")
                task_call_webhook(file_path, file_hash)
                task_mark_as_processed(file_hash)
                stats['processed'] += 1
                slots_available -= 1
            except Exception as e:
                logger.error(f"❌ Failed to process updated file {file_path}: {e}")
                task_mark_as_error(file_hash)
        else:
            logger.info(f"⏸️  Workflow limit reached, skipping remaining updated files")
            stats['skipped'] = len(files) - stats['processed']
            break
    
    return stats


@task(name="process_deleted_files", retries=2, persist_result=True)
def task_process_deleted_files(files: List[Tuple[str, str, int]]) -> int:
    """Task: обработка deleted файлов"""
    processed = 0
    
    for file_path, file_hash, file_size in files:
        try:
            logger.info(f"🗑️  Processing deleted: {file_path}")
            chunks_deleted = task_delete_chunks_by_hash(file_hash)
            task_delete_file(file_hash)
            logger.info(f"✅ Deleted {chunks_deleted} chunks and file record")
            processed += 1
        except Exception as e:
            logger.error(f"❌ Failed to process deleted file {file_path}: {e}")
    
    return processed


@flow(name="file_status_processor_flow")
def file_status_processor_flow():
    """Обработка изменений статусов файлов (added/updated → ingestion, deleted → cleanup)"""
    start_time = time.time()
    
    try:
        # Получаем файлы требующие обработки
        pending = task_get_pending_files()
        
        total_pending = sum(len(files) for files in pending.values())
        
        if total_pending == 0:
            logger.info("📭 No pending files")
            create_table_artifact(
                key="processing-summary",
                table=[
                    {"Metric": "Total processed", "Value": 0},
                    {"Metric": "Added (ingested)", "Value": 0},
                    {"Metric": "Updated (reingested)", "Value": 0},
                    {"Metric": "Deleted (cleaned)", "Value": 0},
                    {"Metric": "Skipped (capacity)", "Value": 0},
                    {"Metric": "Duration (s)", "Value": f"{time.time() - start_time:.2f}"},
                ],
                description="File Status Processor Summary"
            )
            return {
                'success': True,
                'processed': 0,
                'added': 0,
                'updated': 0,
                'deleted': 0,
                'skipped': 0,
                'duration': time.time() - start_time
            }
        
        logger.info(f"📋 Found {total_pending} pending files (added:{len(pending['added'])}, updated:{len(pending['updated'])}, deleted:{len(pending['deleted'])})")
        
        # Проверяем доступные слоты
        current_processed = task_get_processed_count()
        slots_available = file_processor.max_heavy_workflows - current_processed
        logger.info(f"📊 Workflow capacity: {slots_available}/{file_processor.max_heavy_workflows} slots available")
        
        # Обрабатываем added файлы
        added_stats = task_process_added_files(pending['added'], slots_available)
        slots_available -= added_stats['processed']
        
        # Обрабатываем updated файлы
        updated_stats = task_process_updated_files(pending['updated'], slots_available)
        
        # Обрабатываем deleted файлы (не занимают слоты)
        deleted_count = task_process_deleted_files(pending['deleted'])
        
        duration = time.time() - start_time
        total_processed = added_stats['processed'] + updated_stats['processed'] + deleted_count
        total_skipped = added_stats['skipped'] + updated_stats['skipped']
        
        logger.info(
            f"✅ Processed {total_processed} files "
            f"(+{added_stats['processed']}, ~{updated_stats['processed']}, -{deleted_count}, "
            f"skipped:{total_skipped}) in {duration:.2f}s"
        )
        
        # Создаём артефакт с результатами обработки
        create_table_artifact(
            key="processing-summary",
            table=[
                {"Metric": "Total processed", "Value": total_processed},
                {"Metric": "Added (ingested)", "Value": added_stats['processed']},
                {"Metric": "Updated (reingested)", "Value": updated_stats['processed']},
                {"Metric": "Deleted (cleaned)", "Value": deleted_count},
                {"Metric": "Skipped (capacity)", "Value": total_skipped},
                {"Metric": "Duration (s)", "Value": f"{duration:.2f}"},
            ],
            description="File Status Processor Summary"
        )
        
        return {
            'success': True,
            'processed': total_processed,
            'added': added_stats['processed'],
            'updated': updated_stats['processed'],
            'deleted': deleted_count,
            'skipped': total_skipped,
            'duration': duration
        }
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"❌ Processing failed after {duration:.2f}s: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    # Защита от дублирования процессов (как HTTP сервер проверяет порт)
    process_lock = ProcessLock('/tmp/alpaca_rag.pid')
    process_lock.acquire()
    process_lock.setup_handlers()
    
    try:
        logger.info("Starting ALPACA RAG system...")
        logger.info(f"Monitored folder: {settings.MONITORED_PATH}")
        logger.info(f"File watcher interval: {settings.SCAN_MONITORED_FOLDER_INTERVAL}s")
        logger.info(f"Status processor interval: {settings.PROCESS_FILE_CHANGES_INTERVAL}s")
        logger.info(f"Max heavy workflows: {settings.MAX_HEAVY_WORKFLOWS}")
        
        # Сброс статусов processed у файлов в базе при старте
        reset_count = task_reset_processed()
        
        # Запуск нескольких flows
        serve(
            file_watcher_flow.to_deployment(
                name="file-watcher",
                interval=timedelta(seconds=settings.SCAN_MONITORED_FOLDER_INTERVAL),
                description="Сканирование и синхронизация файлов"
            ),
            file_status_processor_flow.to_deployment(
                name="file-status-processor",
                interval=timedelta(seconds=settings.PROCESS_FILE_CHANGES_INTERVAL),
                description="Обработка изменений статусов файлов"
            )
        )
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
    finally:
        process_lock.release()
