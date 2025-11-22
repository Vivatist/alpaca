"""
File Watcher Service - изолированный сервис для мониторинга файлов
"""
import time
from typing import Dict, Any
from app.utils.logging import get_logger
from .file_watcher.scanner import Scanner
from .file_watcher.database import Database
from .file_watcher.vector_sync import VectorSync
from .file_watcher.file_filter import FileFilter


logger = get_logger(__name__)


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
        Выполняет полный цикл сканирования и синхронизации
        
        Returns:
            dict: Результаты сканирования и синхронизации
        """
        start_time = time.time()
        
        try:
            # Сканируем диск
            files = self.scanner.scan()
            logger.info(f"Found {len(files)} files on disk")
            
            # Синхронизируем файлы с БД
            file_sync = self.db.sync_by_hash(files)
            logger.info(
                f"File sync: "
                f"+{file_sync['added']} added, "
                f"~{file_sync['updated']} updated, "
                f"-{file_sync['deleted']} deleted, "
                f"={file_sync['unchanged']} unchanged"
            )
            
            # Синхронизируем статусы
            status_sync = self.vector_sync.sync_status()
            logger.info(
                f"Status sync: "
                f"ok={status_sync['ok']}, "
                f"added={status_sync['added']}, "
                f"updated={status_sync['updated']}, "
                f"unchanged={status_sync['unchanged']}"
            )
            
            duration = time.time() - start_time
            
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
            return {
                'success': False,
                'error': str(e),
                'duration': duration
            }
    
    def reset_processed_statuses(self) -> int:
        """
        Сбрасывает все статусы 'processed' на 'ok'
        
        Returns:
            int: Количество сброшенных записей
        """
        return self.db.reset_processed_to_ok()
