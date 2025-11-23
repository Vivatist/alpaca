"""
File Watcher Service - изолированный сервис для мониторинга файлов
"""
from typing import Dict, Any
from prefect import task
from utils.logging import get_logger
from .scanner import Scanner
from .database import Database
from .vector_sync import VectorSync
from .file_filter import FileFilter


logger = get_logger(__name__)


# Prefect tasks для file watcher
@task(name="scan_disk", retries=3, persist_result=True)
def task_scan_disk(scanner: Scanner) -> list:
    """Task: сканирование диска"""
    return scanner.scan()


@task(name="sync_files_to_db", retries=3, persist_result=True)
def task_sync_files(db: Database, files: list) -> dict:
    """Task: синхронизация файлов с БД по хешам"""
    return db.sync_by_hash(files)


@task(name="sync_vector_status", retries=3, persist_result=True)
def task_sync_status(vector_sync) -> dict:
    """Task: синхронизация статусов с векторной БД"""
    return vector_sync.sync_status()


@task(name="reset_processed_statuses", persist_result=True)
def task_reset_processed(db: Database) -> int:
    """Task: сброс статусов 'processed' на 'ok'"""
    count = db.reset_processed_to_ok()
    if count > 0:
        logger.info(f"🔄 Reset {count} processed statuses")
    return count


class FileWatcherService:
    """Сервис для мониторинга файлов и синхронизации с БД"""
    
    def __init__(
        self,
        database_url: str,
        monitored_path: str,
        allowed_extensions: list[str],
        file_min_size: int = 100,
        file_max_size: int = 10 * 1024 * 1024,
        excluded_dirs: list[str] = None,
        excluded_patterns: list[str] = None
    ):
        """
        Args:
            database_url: URL подключения к базе данных
            monitored_path: Путь к отслеживаемой папке
            allowed_extensions: Список разрешённых расширений
            file_min_size: Минимальный размер файла в байтах
            file_max_size: Максимальный размер файла в байтах
            excluded_dirs: Исключённые директории
            excluded_patterns: Исключённые паттерны файлов
        """
        self.db = Database(database_url=database_url)
        
        file_filter = FileFilter(
            min_size=file_min_size,
            max_size=file_max_size,
            excluded_dirs=excluded_dirs or ['TMP'],
            excluded_patterns=excluded_patterns or ['~*', '.*']
        )
        
        self.scanner = Scanner(
            monitored_path=monitored_path,
            allowed_extensions=allowed_extensions,
            file_filter=file_filter
        )
        
        self.vector_sync = VectorSync(self.db)
    
    def scan_and_sync(self) -> Dict[str, Any]:
        """
        Выполняет полный цикл сканирования и синхронизации.
        Использует Prefect tasks для каждого шага.
        
        Returns:
            dict: Результаты сканирования и синхронизации
        """
        import time
        start_time = time.time()
        
        try:
            # Каждый шаг - отдельная task с retry и мониторингом
            files = task_scan_disk(self.scanner)
            file_sync = task_sync_files(self.db, files)
            # NOTE: vector_sync отключен - логика синхронизации статусов теперь в sync_by_hash
            # status_sync = task_sync_status(self.vector_sync)
            
            duration = time.time() - start_time
            logger.info(
                f"disc[total:{len(files)}, "
                f"+{file_sync['added']}, "
                f"~{file_sync['updated']}, "
                f"-{file_sync['deleted']}, "
                f"ok:{file_sync['unchanged']}] "
                f"in {duration:.2f}s"
            )
            
            return {
                'success': True,
                'disk_files': len(files),
                'file_sync': file_sync,
                'duration': duration
            }
            
        except Exception as e:
            import time
            duration = time.time() - start_time
            logger.error(f"❌ Scan failed after {duration:.2f}s: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'duration': duration
            }
    
    def scan(self) -> list:
        """
        Сканирует диск и возвращает список файлов.
        
        Returns:
            list: Список словарей с информацией о файлах
        """
        return self.scanner.scan()
    
    def sync_by_hash(self, files: list) -> Dict[str, int]:
        """
        Синхронизирует файлы с БД по хешам.
        
        Args:
            files: Список файлов с диска
            
        Returns:
            dict: Статистика (added, updated, deleted, unchanged)
        """
        return self.db.sync_by_hash(files)
    
    def sync_status(self) -> Dict[str, int]:
        """
        Синхронизирует статусы файлов с векторной БД.
        
        Returns:
            dict: Статистика (ok, added, updated)
        """
        return self.vector_sync.sync_status()
    
    def reset_processed_statuses(self) -> int:
        """
        Сбрасывает все статусы 'processed' на 'ok'.
        
        Returns:
            int: Количество сброшенных записей
        """
        count = self.db.reset_processed_to_ok()
        return count
