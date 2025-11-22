import os
from pathlib import Path
from typing import List, Set
import fnmatch


class FileFilter:
    """Фильтрация файлов по размеру, имени и папкам"""
    
    def __init__(
        self,
        min_size: int = 500,
        max_size: int = 10 * 1024 * 1024,
        excluded_dirs: List[str] = None,
        excluded_patterns: List[str] = None
    ):
        """
        Args:
            min_size: Минимальный размер файла в байтах (по умолчанию 500)
            max_size: Максимальный размер файла в байтах (по умолчанию 10 МБ)
            excluded_dirs: Список папок для игнорирования (например, ['TMP', '.git'])
            excluded_patterns: Список шаблонов имен файлов для игнорирования (например, ['~*', '.*'])
        """
        self.min_size = min_size
        self.max_size = max_size
        self.excluded_dirs: Set[str] = set(excluded_dirs or [])
        self.excluded_patterns: List[str] = excluded_patterns or []
    
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
            stat_info: Опциональный stat_result для оптимизации (если уже получен)
        
        Returns:
            True если файл нужно пропустить, False если обрабатывать
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
    
    @staticmethod
    def from_env() -> 'FileFilter':
        """Создает FileFilter из переменных окружения"""
        min_size = int(os.getenv('FILE_MIN_SIZE', '500'))
        max_size = int(os.getenv('FILE_MAX_SIZE', str(10 * 1024 * 1024)))
        
        # Парсинг списка исключенных папок (через запятую)
        excluded_dirs_str = os.getenv('EXCLUDED_DIRS', 'TMP')
        excluded_dirs = [d.strip() for d in excluded_dirs_str.split(',') if d.strip()]
        
        # Парсинг списка шаблонов исключения (через запятую)
        excluded_patterns_str = os.getenv('EXCLUDED_PATTERNS', '~*,.*')
        excluded_patterns = [p.strip() for p in excluded_patterns_str.split(',') if p.strip()]
        
        return FileFilter(
            min_size=min_size,
            max_size=max_size,
            excluded_dirs=excluded_dirs,
            excluded_patterns=excluded_patterns
        )
