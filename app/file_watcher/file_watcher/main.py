"""File Watcher - минималистичный сканер файлов

Только периодическое сканирование и обновление file_state:
1. Сканирует диск каждые SCAN_INTERVAL секунд
2. Синхронизирует file_state с диском
3. Обновляет status_sync через сравнение с documents
"""

from database import Database
from scanner import Scanner
from vector_sync import VectorSync
import os
import time
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Конфигурация из environment
MONITORED_PATH = os.getenv('MONITORED_PATH', '/monitored_folder')
ALLOWED_EXTENSIONS = os.getenv('ALLOWED_EXTENSIONS', '.docx,.pdf').split(',')
SCAN_INTERVAL = int(os.getenv('SCAN_INTERVAL', '20'))

# Инициализация
db = Database()
scanner = Scanner(MONITORED_PATH, ALLOWED_EXTENSIONS)
vector_sync = VectorSync(db)

# Счётчик циклов
scan_cycle_counter = 0


def perform_scan():
    """Выполняет сканирование и обновляет file_state и status_sync"""
    global scan_cycle_counter
    scan_cycle_counter += 1
    
    start_time = time.time()
    
    try:
        # Шаг 1: Сканируем диск
        files = scanner.scan()
        
        # Шаг 2: Синхронизируем file_state с диском
        file_state_sync = db.sync_by_hash(files)
        
        # Шаг 3: Сравниваем file_state с documents и обновляем status_sync
        status_sync_result = vector_sync.sync_status()
        
        duration = time.time() - start_time
        
        logger.info(
            f"Cycle #{scan_cycle_counter}: "
            f"disk={len(files)}, "
            f"file_state: +{file_state_sync['added']} ~{file_state_sync['updated']} -{file_state_sync['deleted']}, "
            f"status: ok={status_sync_result['ok']} added={status_sync_result['added']} upd={status_sync_result['updated']} "
            f"({duration:.2f}s)"
        )
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Cycle #{scan_cycle_counter} ERROR: {e}", exc_info=True)


def main():
    """Основной цикл сканирования"""
    logger.info("=== File Watcher started ===")
    logger.info(f"Monitored path: {MONITORED_PATH}")
    logger.info(f"Extensions: {ALLOWED_EXTENSIONS}")
    logger.info(f"Scan interval: {SCAN_INTERVAL}s")
    logger.info("")
    
    # Сбрасываем все статусы 'processed' на 'ok' при старте
    try:
        reset_count = db.reset_processed_to_ok()
        if reset_count > 0:
            logger.info(f"Reset {reset_count} 'processed' statuses to 'ok'")
    except Exception as e:
        logger.error(f"Error resetting processed statuses: {e}")
    
    # Первое сканирование сразу при старте
    perform_scan()
    
    # Бесконечный цикл
    while True:
        time.sleep(SCAN_INTERVAL)
        perform_scan()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n=== File Watcher stopped ===")
