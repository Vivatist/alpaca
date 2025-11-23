"""
File Status Processor Service - обработка изменений файлов
"""
import time
import requests
from typing import Dict, List, Tuple, Any
from prefect import task
from utils.logging import get_logger
from .database import Database


logger = get_logger(__name__)


# Prefect tasks для file status processor
@task(name="get_pending_files", retries=2, persist_result=True)
def task_get_pending_files(db: Database) -> Dict[str, List[Tuple]]:
    """Task: получение файлов требующих обработки"""
    return db.get_pending_files()


@task(name="get_processed_count", retries=2, persist_result=True)
def task_get_processed_count(db: Database) -> int:
    """Task: получение количества файлов в обработке"""
    return db.get_processed_count()


@task(name="call_ingestion_webhook", retries=3, persist_result=True)
def task_call_webhook(webhook_url: str, file_path: str, file_hash: str) -> bool:
    """Task: вызов webhook для ingestion"""
    response = requests.post(webhook_url, json={
        'file_path': file_path,
        'file_hash': file_hash,
        'operation': 'process_document'
    }, timeout=5)
    response.raise_for_status()
    return True


@task(name="delete_chunks_by_path", retries=2, persist_result=True)
def task_delete_chunks_by_path(db: Database, file_path: str) -> int:
    """Task: удаление chunks по пути"""
    return db.delete_chunks_by_path(file_path)


@task(name="delete_chunks_by_hash", retries=2, persist_result=True)
def task_delete_chunks_by_hash(db: Database, file_hash: str) -> int:
    """Task: удаление chunks по хэшу"""
    return db.delete_chunks_by_hash(file_hash)


@task(name="mark_as_processed", persist_result=True)
def task_mark_as_processed(db: Database, file_hash: str) -> bool:
    """Task: пометка файла как processed"""
    return db.mark_as_processed(file_hash)


@task(name="mark_as_error", persist_result=True)
def task_mark_as_error(db: Database, file_hash: str) -> bool:
    """Task: пометка файла как error"""
    return db.mark_as_error(file_hash)


@task(name="delete_file_by_hash", persist_result=True)
def task_delete_file(db: Database, file_hash: str) -> bool:
    """Task: удаление записи файла"""
    return db.delete_file_by_hash(file_hash)


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
                task_call_webhook(webhook_url, file_path, file_hash)
                task_mark_as_processed(db, file_hash)
                stats['processed'] += 1
                slots_available -= 1
            except Exception as e:
                logger.error(f"❌ Failed to process added file {file_path}: {e}")
                task_mark_as_error(db, file_hash)
        else:
            logger.info(f"⏸️  Workflow limit reached, skipping remaining added files")
            stats['skipped'] = len(files) - stats['processed']
            break
    
    return stats


@task(name="process_updated_files", retries=2, persist_result=True)
def task_process_updated_files(
    db: Database,
    webhook_url: str,
    files: List[Tuple[str, str, int]],
    slots_available: int
) -> Dict[str, int]:
    """Task: обработка updated файлов"""
    stats = {'processed': 0, 'skipped': 0}
    
    for file_path, file_hash, file_size in files:
        if slots_available > 0:
            try:
                logger.info(f"🔄 Processing updated: {file_path}")
                chunks_deleted = task_delete_chunks_by_path(db, file_path)
                logger.info(f"🗑️  Deleted {chunks_deleted} old chunks")
                task_call_webhook(webhook_url, file_path, file_hash)
                task_mark_as_processed(db, file_hash)
                stats['processed'] += 1
                slots_available -= 1
            except Exception as e:
                logger.error(f"❌ Failed to process updated file {file_path}: {e}")
                task_mark_as_error(db, file_hash)
        else:
            logger.info(f"⏸️  Workflow limit reached, skipping remaining updated files")
            stats['skipped'] = len(files) - stats['processed']
            break
    
    return stats




class FileStatusProcessorService:
    """Сервис для обработки изменений статусов файлов"""
    
    def __init__(
        self,
        database_url: str,
        webhook_url: str,
        max_heavy_workflows: int = 2
    ):
        """
        Args:
            database_url: URL подключения к базе данных
            webhook_url: URL webhook для запуска ingestion pipeline
            max_heavy_workflows: Максимум тяжёлых воркфлоу одновременно
        """
        self.db = Database(database_url=database_url)
        self.webhook_url = webhook_url
        self.max_heavy_workflows = max_heavy_workflows
    
    def process_changes(self) -> Dict[str, Any]:
        """
        Обработка изменений файлов.
        Вызывает Prefect tasks для каждого шага.
        
        Returns:
            dict: Результаты обработки
        """
        start_time = time.time()
        
        try:
            # Получаем файлы требующие обработки
            pending = task_get_pending_files(self.db)
            
            total_pending = sum(len(files) for files in pending.values())
            
            if total_pending == 0:
                logger.info("📭 No pending files")
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
            current_processed = task_get_processed_count(self.db)
            slots_available = self.max_heavy_workflows - current_processed
            logger.info(f"📊 Workflow capacity: {slots_available}/{self.max_heavy_workflows} slots available")
            
            # Обрабатываем added файлы
            added_stats = task_process_added_files(
                self.db,
                self.webhook_url,
                pending['added'],
                slots_available
            )
            slots_available -= added_stats['processed']
            
            # Обрабатываем updated файлы
            updated_stats = task_process_updated_files(
                self.db,
                self.webhook_url,
                pending['updated'],
                slots_available
            )
            
            # Обрабатываем deleted файлы (не занимают слоты)
            deleted_count = task_process_deleted_files(self.db, pending['deleted'])
            
            duration = time.time() - start_time
            total_processed = added_stats['processed'] + updated_stats['processed'] + deleted_count
            total_skipped = added_stats['skipped'] + updated_stats['skipped']
            
            logger.info(
                f"✅ Processed {total_processed} files "
                f"(+{added_stats['processed']}, ~{updated_stats['processed']}, -{deleted_count}, "
                f"skipped:{total_skipped}) in {duration:.2f}s"
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
            return {
                'success': False,
                'error': str(e),
                'duration': duration
            }
    
    def get_pending_files(self) -> Dict[str, List[Tuple]]:
        """Получение файлов требующих обработки"""
        return self.db.get_pending_files()
    
    def get_processed_count(self) -> int:
        """Получение количества файлов в обработке"""
        return self.db.get_processed_count()
    
    def call_webhook(self, file_path: str, file_hash: str) -> bool:
        """Вызов webhook для ingestion"""
        response = requests.post(self.webhook_url, json={
            'file_path': file_path,
            'file_hash': file_hash,
            'operation': 'process_document'
        }, timeout=5)
        response.raise_for_status()
        return True
    
    def delete_chunks_by_path(self, file_path: str) -> int:
        """Удаление chunks по пути"""
        return self.db.delete_chunks_by_path(file_path)
    
    def delete_chunks_by_hash(self, file_hash: str) -> int:
        """Удаление chunks по хэшу"""
        return self.db.delete_chunks_by_hash(file_hash)
    
    def mark_as_processed(self, file_hash: str) -> bool:
        """Пометка файла как processed"""
        return self.db.mark_as_processed(file_hash)
    
    def mark_as_error(self, file_hash: str) -> bool:
        """Пометка файла как error"""
        return self.db.mark_as_error(file_hash)
    
    def delete_file(self, file_hash: str) -> bool:
        """Удаление записи файла"""
        return self.db.delete_file_by_hash(file_hash)
