"""
ALPACA RAG - Единая точка входа
"""
import os
import sys
import warnings
import logging
import atexit
import signal

os.environ.setdefault("PYTHONWARNINGS", "ignore::UserWarning")
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic_settings.main")

# Отключаем логирование Prefect ДО импорта
os.environ["PREFECT_LOGGING_LEVEL"] = "WARNING"
os.environ["PREFECT_LOGGING_TO_API_ENABLED"] = "false"

from datetime import timedelta
from prefect import flow, serve
from prefect.artifacts import create_table_artifact
from app.utils.logging import setup_logging, get_logger
from app.file_watcher import FileWatcherService
from app.flows.file_status_processor import FileStatusProcessorService
from settings import settings

# Настраиваем логирование в каждом процессе
setup_logging()
logger = get_logger(__name__)

# PID файл для защиты от дублей (как у HTTP сервера)
PID_FILE = '/tmp/alpaca_rag.pid'


def acquire_lock():
    """Проверяет что процесс не запущен (аналог bind() у сокета)"""
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, 'r') as f:
                old_pid = int(f.read().strip())
            
            # Проверяем жив ли процесс
            try:
                os.kill(old_pid, 0)  # Не убивает, просто проверяет
                logger.error(f"❌ ALPACA RAG already running (PID: {old_pid})")
                logger.error(f"   To stop: kill {old_pid}")
                logger.error(f"   Or if it's dead: rm {PID_FILE}")
                sys.exit(1)
            except OSError:
                # Процесс мёртв, удаляем старый PID
                logger.info(f"Removing stale PID file (process {old_pid} is dead)")
                os.remove(PID_FILE)
        except (ValueError, IOError) as e:
            logger.warning(f"Invalid PID file, removing: {e}")
            os.remove(PID_FILE)
    
    # Записываем наш PID
    with open(PID_FILE, 'w') as f:
        f.write(str(os.getpid()))
    logger.info(f"Acquired lock (PID: {os.getpid()}, file: {PID_FILE})")


def release_lock():
    """Удаляет PID файл при завершении"""
    try:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
            logger.info("Released lock")
    except Exception as e:
        logger.error(f"Failed to release lock: {e}")


def signal_handler(signum, frame):
    """Обработчик сигналов для graceful shutdown"""
    logger.info(f"Received signal {signum}, shutting down...")
    release_lock()
    sys.exit(0)

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


@flow(name="file_watcher_flow")
def file_watcher_flow():
    """Сканирование и синхронизация файлов"""
    result = file_watcher.scan_and_sync()

    if result['success']:
        # Создаём артефакт с результатами сканирования
        create_table_artifact(
            key="scan-summary",
            table=[
                {"Metric": "Files on disk", "Value": result['disk_files']},
                {"Metric": "Added", "Value": result['file_sync']['added']},
                {"Metric": "Updated", "Value": result['file_sync']['updated']},
                {"Metric": "Deleted", "Value": result['file_sync']['deleted']},
                {"Metric": "Unchanged", "Value": result['file_sync']['unchanged']},
                {"Metric": "Status OK", "Value": result['status_sync']['ok']},
                {"Metric": "Status Added", "Value": result['status_sync']['added']},
                {"Metric": "Status Updated", "Value": result['status_sync']['updated']},
                {"Metric": "Duration (s)", "Value": f"{result['duration']:.2f}"},
            ],
            description="File Watcher Scan Summary"
        )
    else:
        raise Exception(result.get('error', 'Unknown error'))
    
    return result


@flow(name="file_status_processor_flow")
def file_status_processor_flow():
    """Обработка изменений статусов файлов (added/updated → ingestion, deleted → cleanup)"""
    result = file_processor.process_changes()

    if result['success']:
        # Создаём артефакт с результатами обработки
        create_table_artifact(
            key="processing-summary",
            table=[
                {"Metric": "Total processed", "Value": result['processed']},
                {"Metric": "Added (ingested)", "Value": result['added']},
                {"Metric": "Updated (reingested)", "Value": result['updated']},
                {"Metric": "Deleted (cleaned)", "Value": result['deleted']},
                {"Metric": "Skipped (capacity)", "Value": result['skipped']},
                {"Metric": "Duration (s)", "Value": f"{result['duration']:.2f}"},
            ],
            description="File Status Processor Summary"
        )
    else:
        raise Exception(result.get('error', 'Unknown error'))
    
    return result


if __name__ == "__main__":
    # Проверяем что мы единственные (как HTTP сервер проверяет порт)
    acquire_lock()
    
    # Регистрируем очистку при выходе
    atexit.register(release_lock)
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        logger.info("Starting ALPACA RAG system...")
        logger.info(f"Monitored folder: {settings.MONITORED_PATH}")
        logger.info(f"File watcher interval: {settings.SCAN_MONITORED_FOLDER_INTERVAL}s")
        logger.info(f"Status processor interval: {settings.PROCESS_FILE_CHANGES_INTERVAL}s")
        logger.info(f"Max heavy workflows: {settings.MAX_HEAVY_WORKFLOWS}")
        
        # Сброс статусов processed у файлов в базе при старте
        reset_count = file_watcher.reset_processed_statuses()
        
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
        release_lock()
