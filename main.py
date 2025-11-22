"""
ALPACA RAG - Единая точка входа
"""
import os
import warnings

# Подавляем предупреждения pydantic-settings о неиспользуемых ключах конфигурации
os.environ.setdefault("PYTHONWARNINGS", "ignore::UserWarning")
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic_settings.main")

import time
from datetime import timedelta
from prefect import flow, serve
from app.utils.logging import setup_logging, get_logger
from app.file_watcher import Scanner, Database, VectorSync
from settings import settings

# Настраиваем логирование при старте приложения
setup_logging()

logger = get_logger(__name__)

# Инициализация компонентов file-watcher
db = Database(database_url=settings.DATABASE_URL)
scanner = Scanner(
    monitored_path=settings.MONITORED_PATH,
    allowed_extensions=settings.ALLOWED_EXTENSIONS.split(',')
)
vector_sync = VectorSync(db)

# Счётчик циклов
scan_cycle_counter = 0


@flow(name="file_watcher_flow", log_prints=True)
def file_watcher_flow():
    """Flow для сканирования файлов и синхронизации с БД"""
    global scan_cycle_counter
    scan_cycle_counter += 1
    
    start_time = time.time()
    
    try:
        logger.info(f"🔍 Cycle #{scan_cycle_counter}: Starting file scan...")
        
        # Шаг 1: Сканируем диск
        files = scanner.scan()
        logger.info(f"📁 Found {len(files)} files on disk")
        
        # Шаг 2: Синхронизируем file_state с диском
        file_state_sync = db.sync_by_hash(files)
        logger.info(
            f"💾 File state sync: "
            f"+{file_state_sync['added']} added, "
            f"~{file_state_sync['updated']} updated, "
            f"-{file_state_sync['deleted']} deleted, "
            f"={file_state_sync['unchanged']} unchanged"
        )
        
        # Шаг 3: Сравниваем file_state с documents и обновляем status_sync
        status_sync_result = vector_sync.sync_status()
        logger.info(
            f"🔄 Status sync: "
            f"ok={status_sync_result['ok']}, "
            f"added={status_sync_result['added']}, "
            f"updated={status_sync_result['updated']}, "
            f"unchanged={status_sync_result['unchanged']}"
        )
        
        duration = time.time() - start_time
        logger.info(f"✅ Cycle #{scan_cycle_counter} completed in {duration:.2f}s")
        
        return {
            'cycle': scan_cycle_counter,
            'disk_files': len(files),
            'file_state_sync': file_state_sync,
            'status_sync': status_sync_result,
            'duration': duration
        }
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"❌ Cycle #{scan_cycle_counter} failed after {duration:.2f}s: {e}", exc_info=True)
        raise


def start_deployment_server():
    """Запуск Prefect deployment с file-watcher flow"""
    logger.info("🚀 Starting ALPACA RAG system...")
    logger.info(f"📁 Monitored path: {settings.MONITORED_PATH}")
    logger.info(f"📄 Allowed extensions: {settings.ALLOWED_EXTENSIONS}")
    logger.info(f"⏱️  Scan interval: {settings.SCAN_INTERVAL}s")
    
    # Сбрасываем все статусы 'processed' на 'ok' при старте
    try:
        reset_count = db.reset_processed_to_ok()
        if reset_count > 0:
            logger.info(f"🔄 Reset {reset_count} 'processed' statuses to 'ok'")
    except Exception as e:
        logger.error(f"❌ Error resetting processed statuses: {e}")
    
    logger.info("Starting Prefect deployment server...")
    
    # Создаём deployment с периодическим сканированием
    serve(
        file_watcher_flow.to_deployment(
            name="file-watcher-deployment",
            interval=timedelta(seconds=settings.SCAN_INTERVAL),
            description=f"Сканирование файлов и синхронизация с БД каждые {settings.SCAN_INTERVAL} секунд"
        )
    )


if __name__ == "__main__":
    try:
        start_deployment_server()
    except KeyboardInterrupt:
        logger.info("Shutting down ALPACA RAG system...")
    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
        raise
