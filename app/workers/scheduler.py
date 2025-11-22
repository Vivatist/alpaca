"""
Scheduler для периодических задач с Prefect
"""

import asyncio
import logging
from datetime import timedelta

from prefect import flow, task, serve

from settings import settings
from app.core.file_watcher import FileScanner
from app.db.connection import get_db
from app.workers.file_processor import process_queue_flow

logger = logging.getLogger(__name__)


@task(
    name="Scan Files",
    description="Сканирует файловую систему и обновляет file_state"
)
async def scan_files_task() -> dict:
    """
    Сканирует monitored_path и синхронизирует с БД
    
    Returns:
        Статистика сканирования
    """
    logger.info(f"🔍 Scanning {settings.MONITORED_PATH}")
    
    scanner = FileScanner()
    disk_files = scanner.scan()
    
    logger.info(f"Found {len(disk_files)} files on disk")
    
    # Синхронизация с БД
    stats = await sync_files_with_db(disk_files)
    
    logger.info(
        f"Sync stats: {stats['added']} added, {stats['updated']} updated, "
        f"{stats['unchanged']} unchanged, {stats['deleted']} deleted"
    )
    
    return stats


async def sync_files_with_db(disk_files: list) -> dict:
    """
    Синхронизирует файлы с диска с БД (портировано из database.py)
    
    Args:
        disk_files: Список файлов с диска
    
    Returns:
        Статистика операций
    """
    stats = {
        'added': 0,
        'updated': 0,
        'unchanged': 0,
        'deleted': 0
    }
    
    async with get_db() as db:
        # Получаем все хэши и пути из БД
        db_records = await db.fetch("SELECT file_hash, file_path FROM file_state")
        db_hashes = {row['file_hash']: row['file_path'] for row in db_records}
        db_paths = {row['file_path']: row['file_hash'] for row in db_records}
        
        # Создаём множества хэшей и путей с диска
        disk_hashes = {f['hash']: f for f in disk_files}
        disk_paths = {f['path'] for f in disk_files}
        
        # Классифицируем файлы
        for disk_hash, disk_file in disk_hashes.items():
            if disk_hash in db_hashes:
                # Хэш существует - файл не изменился
                stats['unchanged'] += 1
            else:
                # Новый хэш - проверяем, есть ли файл с таким путём в БД
                if disk_file['path'] in db_paths:
                    # Путь есть, но хэш другой = файл изменился
                    stats['updated'] += 1
                else:
                    # Ни пути, ни хэша нет = новый файл
                    stats['added'] += 1
        
        # Батчинг вставки/обновления для файлов с диска
        if disk_files:
            for disk_file in disk_files:
                # Используем ON CONFLICT для upsert
                await db.execute("""
                    INSERT INTO file_state (file_path, file_size, file_hash, file_mtime, last_checked, status_sync)
                    VALUES ($1, $2, $3, $4, NOW(), 'added')
                    ON CONFLICT (file_path) DO UPDATE SET
                        file_size = CASE 
                            WHEN file_state.status_sync = 'processed' THEN file_state.file_size
                            WHEN file_state.status_sync = 'error' THEN file_state.file_size
                            ELSE EXCLUDED.file_size
                        END,
                        file_hash = CASE 
                            WHEN file_state.status_sync = 'processed' THEN file_state.file_hash
                            WHEN file_state.status_sync = 'error' THEN file_state.file_hash
                            ELSE EXCLUDED.file_hash
                        END,
                        file_mtime = CASE 
                            WHEN file_state.status_sync = 'processed' THEN file_state.file_mtime
                            WHEN file_state.status_sync = 'error' THEN file_state.file_mtime
                            ELSE EXCLUDED.file_mtime
                        END,
                        last_checked = NOW(),
                        status_sync = CASE 
                            WHEN file_state.status_sync = 'error' THEN 'error'
                            WHEN file_state.status_sync = 'processed' THEN 'processed'
                            WHEN file_state.status_sync = 'deleted' THEN 'updated'
                            WHEN file_state.file_hash != EXCLUDED.file_hash THEN 'updated'
                            ELSE file_state.status_sync
                        END
                """, disk_file['path'], disk_file['size'], disk_file['hash'], disk_file['mtime'])
        
        # Помечаем файлы, которых нет на диске, как deleted
        missing_paths = set(db_paths.keys()) - disk_paths
        if missing_paths:
            for path in missing_paths:
                result = await db.execute("""
                    UPDATE file_state 
                    SET status_sync = 'deleted', last_checked = NOW()
                    WHERE file_path = $1
                      AND status_sync NOT IN ('deleted', 'error')
                """, path)
            stats['deleted'] = len(missing_paths)
    
    return stats


@flow(
    name="File Watcher",
    description="Периодическое сканирование файлов",
    log_prints=True
)
async def file_watcher_flow() -> dict:
    """
    Сканирует файлы и обновляет file_state
    
    Returns:
        Статистика сканирования
    """
    return await scan_files_task()


@flow(
    name="Main Orchestrator",
    description="Главный оркестратор: сканирование + обработка",
    log_prints=True
)
async def main_orchestrator_flow():
    """
    Главный flow который запускает все задачи
    
    1. Сканирует файлы (file_watcher)
    2. Обрабатывает очередь (process_queue)
    """
    logger.info("🎯 Starting main orchestrator")
    
    # 1. Сканирование файлов
    scan_stats = await file_watcher_flow()
    logger.info(f"Scan completed: {scan_stats}")
    
    # 2. Обработка очереди
    process_stats = await process_queue_flow()
    logger.info(f"Processing completed: {process_stats}")
    
    return {
        'scan': scan_stats,
        'processing': process_stats
    }


async def serve_flows():
    """
    Запускает Prefect flows с расписанием (Prefect 3.x API)
    """
    logger.info("🚀 Starting Prefect flows...")
    
    # Запуск flows с расписанием через serve()
    await serve(
        file_watcher_flow.to_deployment(
            name="file-watcher-periodic",
            interval=settings.SCAN_INTERVAL,
            tags=["file-watcher", "periodic"]
        ),
        main_orchestrator_flow.to_deployment(
            name="main-orchestrator",
            interval=60,  # каждую минуту
            tags=["orchestrator", "main"]
        )
    )


async def run_once():
    """
    Запускает одну итерацию main orchestrator (для тестирования)
    """
    await main_orchestrator_flow()


if __name__ == "__main__":
    # Для тестирования: запускает одну итерацию
    asyncio.run(run_once())
