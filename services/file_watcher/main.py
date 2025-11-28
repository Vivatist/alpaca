#!/usr/bin/env python3
"""
File Watcher Service - автономный контейнер для мониторинга файлов
"""
import os
import sys
import time
import signal
from pathlib import Path

# Добавляем src/ в PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from settings import settings
from service import FileWatcherService
from logging_simple import setup_logging, get_logger

# Настраиваем логирование
setup_logging()
logger = get_logger("file-watcher")

# Флаг для graceful shutdown
shutdown_requested = False


def signal_handler(signum, frame):
    """Обработчик сигналов для graceful shutdown"""
    global shutdown_requested
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_requested = True


def run_pre_launch_tests():
    """Запускает ВСЕ тесты перед стартом если PRE_LAUNCH_TESTS=True"""
    if not settings.PRE_LAUNCH_TESTS:
        return
    
    logger.info("🧪 Running pre-launch tests (all modules)...")
    
    try:
        # Добавляем tests/ в путь
        tests_path = Path(__file__).resolve().parent / "tests"
        sys.path.insert(0, str(tests_path))
        
        from run_all_tests import run_all_tests
        
        success = run_all_tests()
        
        if success:
            logger.info("✅ All pre-launch tests passed")
        else:
            logger.error("❌ Some pre-launch tests failed")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"❌ Error running pre-launch tests: {e}", exc_info=True)
        sys.exit(1)


def main():
    """Главный цикл file watcher"""
    global shutdown_requested
    
    # Регистрируем обработчики сигналов
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Запускаем тесты если включено
    # run_pre_launch_tests()
    
    logger.info("=" * 60)
    logger.info("File Watcher Service Starting")
    logger.info("=" * 60)
    logger.info(f"Monitored path: {settings.MONITORED_PATH}")
    logger.info(f"Database: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else 'configured'}")
    logger.info(f"Table: {settings.FILES_TABLE_NAME}")
    logger.info(f"Scan interval: {settings.SCAN_INTERVAL_SECONDS}s")
    logger.info(f"Allowed extensions: {settings.ALLOWED_EXTENSIONS}")
    logger.info(f"File size range: {settings.FILE_MIN_SIZE} - {settings.FILE_MAX_SIZE} bytes")
    logger.info(f"Excluded dirs: {settings.EXCLUDED_DIRS}")
    logger.info(f"Excluded patterns: {settings.EXCLUDED_PATTERNS}")
    logger.info("=" * 60)
    
    # Инициализируем сервис
    try:
        file_watcher = FileWatcherService(
            database_url=settings.DATABASE_URL,
            monitored_path=settings.MONITORED_PATH,
            allowed_extensions=settings.ALLOWED_EXTENSIONS.split(','),
            file_min_size=settings.FILE_MIN_SIZE,
            file_max_size=settings.FILE_MAX_SIZE,
            excluded_dirs=settings.EXCLUDED_DIRS.split(','),
            excluded_patterns=settings.EXCLUDED_PATTERNS.split(','),
            table_name=settings.FILES_TABLE_NAME
        )
        
        logger.info("✅ File Watcher Service initialized successfully")
        
        # Сбрасываем статусы processed на ok при старте
        reset_count = file_watcher.reset_processed_statuses()
        if reset_count > 0:
            logger.info(f"🔄 Reset {reset_count} 'processed' statuses to 'ok' on startup")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize File Watcher Service: {e}")
        sys.exit(1)
    
    # Основной цикл
    iteration = 0
    while not shutdown_requested:
        iteration += 1
        
        try:
            result = file_watcher.scan_and_sync()
            
            logger.info(
                f"#{iteration} disc[total:{result['disk_files']}, "
                f"+{result['file_sync']['added']}, "
                f"~{result['file_sync']['updated']}, "
                f"-{result['file_sync']['deleted']}, "
                f"ok:{result['file_sync']['unchanged']}] "
                f"in {result['duration']:.2f}s"
            )
            
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
            break
            
        except Exception as e:
            logger.error(f"❌ Error during scan iteration: {e}", exc_info=True)
        
        # Ждем следующую итерацию
        if not shutdown_requested:
            logger.debug(f"💤 Sleeping for {settings.SCAN_INTERVAL_SECONDS}s...")
            time.sleep(settings.SCAN_INTERVAL_SECONDS)
    
    logger.info("=" * 60)
    logger.info("File Watcher Service Stopped")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
