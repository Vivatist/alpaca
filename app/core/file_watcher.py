"""
Сканирование файловой системы и синхронизация с БД
Портировано из alpaca-n8n/file-watcher
"""

import os
import hashlib
from pathlib import Path
from typing import List, Dict
import fnmatch
import logging

from settings import settings

logger = logging.getLogger(__name__)


class FileFilter:
    """Фильтрация файлов по размеру, имени и папкам"""
    
    def __init__(
        self,
        min_size: int = None,
        max_size: int = None,
        excluded_dirs: List[str] = None,
        excluded_patterns: List[str] = None
    ):
        self.min_size = min_size or settings.FILE_MIN_SIZE
        self.max_size = max_size or settings.FILE_MAX_SIZE
        self.excluded_dirs = set(excluded_dirs or settings.EXCLUDED_DIRS)
        self.excluded_patterns = excluded_patterns or settings.EXCLUDED_PATTERNS
    
    def should_skip_directory(self, dir_name: str) -> bool:
        """Проверяет, нужно ли пропустить директорию"""
        # Скрытые папки
        if dir_name.startswith('.'):
            return True
        
        # Папки из списка исключений
        if dir_name in self.excluded_dirs:
            return True
        
        return False
    
    def should_skip_file(self, file_path: Path, stat_info: os.stat_result = None) -> bool:
        """
        Проверяет, нужно ли пропустить файл
        
        Args:
            file_path: Путь к файлу
            stat_info: Опциональный stat_result для оптимизации
        
        Returns:
            True если файл нужно пропустить
        """
        filename = file_path.name
        
        # Проверка по шаблонам имени файла
        for pattern in self.excluded_patterns:
            if fnmatch.fnmatch(filename, pattern):
                return True
        
        # Проверка размера файла
        if stat_info is None:
            try:
                stat_info = file_path.stat()
            except (OSError, PermissionError):
                return True  # Пропускаем недоступные файлы
        
        file_size = stat_info.st_size
        
        if file_size < self.min_size or file_size > self.max_size:
            return True
        
        return False


class FileScanner:
    """Сканирование файлов в monitored_path"""
    
    def __init__(self, monitored_path: Path = None, allowed_extensions: List[str] = None):
        self.monitored_path = monitored_path or settings.MONITORED_PATH
        self.allowed_extensions = set(
            ext.lower() for ext in (allowed_extensions or settings.ALLOWED_EXTENSIONS)
        )
        self.file_filter = FileFilter()
    
    @staticmethod
    def calculate_hash(filename: str, size: int, mtime: float) -> str:
        """Вычисляет хэш из имени файла, размера и даты изменения"""
        hash_input = f"{filename}|{size}|{mtime}".encode('utf-8')
        return hashlib.sha256(hash_input).hexdigest()
    
    def scan(self) -> List[Dict]:
        """
        Сканирует папку и возвращает список файлов с метаданными
        
        Returns:
            List[Dict]: [{'path': str, 'size': int, 'hash': str, 'mtime': float}, ...]
        """
        files = []
        
        if not self.monitored_path.exists():
            logger.warning(f"Monitored path does not exist: {self.monitored_path}")
            return files
        
        logger.info(f"Scanning {self.monitored_path}")
        
        # Используем os.walk для рекурсивного обхода (быстрее чем rglob)
        for root, dirs, filenames in os.walk(str(self.monitored_path)):
            # Применяем фильтр к директориям
            dirs[:] = [d for d in dirs if not self.file_filter.should_skip_directory(d)]
            
            root_path = Path(root)
            
            for filename in filenames:
                # Фильтр по расширениям сразу по имени (без stat)
                ext = Path(filename).suffix.lower()
                if self.allowed_extensions and ext not in self.allowed_extensions:
                    continue
                
                file_path = root_path / filename
                
                try:
                    # Один stat() вместо двух вызовов (is_file + stat)
                    stat_info = file_path.stat()
                    
                    # Применяем фильтр к файлу
                    if self.file_filter.should_skip_file(file_path, stat_info):
                        continue
                    
                    # Относительный путь от monitored_folder
                    relative_path = str(file_path.relative_to(self.monitored_path))
                    
                    # Вычисляем хэш из имени файла, размера и времени изменения
                    file_hash = self.calculate_hash(
                        filename=relative_path,
                        size=stat_info.st_size,
                        mtime=stat_info.st_mtime
                    )
                    
                    files.append({
                        'path': relative_path,
                        'size': stat_info.st_size,
                        'hash': file_hash,
                        'mtime': stat_info.st_mtime
                    })
                except (OSError, PermissionError) as e:
                    logger.warning(f"Cannot access file {file_path}: {e}")
                    continue
        
        logger.info(f"Found {len(files)} files")
        return files
    
    def count_files(self) -> int:
        """Быстрый подсчет файлов на диске"""
        count = 0
        if not self.monitored_path.exists():
            return count
        
        for root, dirs, filenames in os.walk(str(self.monitored_path)):
            dirs[:] = [d for d in dirs if not self.file_filter.should_skip_directory(d)]
            
            root_path = Path(root)
            for filename in filenames:
                ext = Path(filename).suffix.lower()
                if self.allowed_extensions and ext not in self.allowed_extensions:
                    continue
                
                file_path = root_path / filename
                try:
                    stat_info = file_path.stat()
                    if not self.file_filter.should_skip_file(file_path, stat_info):
                        count += 1
                except (OSError, PermissionError):
                    continue
        
        return count
