"""
ALPACA RAG - Единая точка входа
"""
import os
import warnings
import logging

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
from settings import settings

# Настраиваем логирование в каждом процессе
setup_logging()
logger = get_logger(__name__)

# Единственный экземпляр сервиса
file_watcher = FileWatcherService(
    database_url=settings.DATABASE_URL,
    monitored_path=settings.MONITORED_PATH,
    allowed_extensions=settings.ALLOWED_EXTENSIONS.split(','),
    file_min_size=settings.FILE_MIN_SIZE,
    file_max_size=settings.FILE_MAX_SIZE,
    excluded_dirs=settings.EXCLUDED_DIRS.split(','),
    excluded_patterns=settings.EXCLUDED_PATTERNS.split(',')
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


if __name__ == "__main__":
    logger.info("Starting ALPACA RAG system...")
    logger.info(f"Monitored folder: {settings.MONITORED_PATH}")
    logger.info(f"Scan interval: {settings.SCAN_MONITORED_FOLDER_INTERVAL}s")
    
    # Сброс статусов processed у файлов в базе при старте
    reset_count = file_watcher.reset_processed_statuses()
    
    # Запуск периодического сканирования
    serve(
        file_watcher_flow.to_deployment(
            name="file-watcher",
            interval=timedelta(seconds=settings.SCAN_MONITORED_FOLDER_INTERVAL),
            description="Сканирование и синхронизация файлов"
        )
    )
