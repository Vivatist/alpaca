"""
File Watcher Service - изолированный сервис для мониторинга файлов
"""
from typing import Dict, Any
from scanner import Scanner
from database import Database
from vector_sync import VectorSync
from file_filter import FileFilter

import logging
logger = logging.getLogger(__name__)


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
        excluded_patterns: list[str] = None,
        table_name: str = "files"
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
            table_name: Название таблицы файлов в БД
        """
        self.db = Database(database_url=database_url, table_name=table_name)
        
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
        
        Returns:
            dict: Результаты сканирования и синхронизации
        """
        import time
        start_time = time.time()
        
        try:
            # Сканирование диска
            files = self.scanner.scan()
            
            # Синхронизация с БД
            file_sync = self.db.sync_by_hash(files)
            
            duration = time.time() - start_time
            logger.debug(
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
