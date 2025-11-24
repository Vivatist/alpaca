import os
import hashlib
from pathlib import Path
from typing import List, Dict
from file_filter import FileFilter

class Scanner:
    def __init__(self, monitored_path: str, allowed_extensions: List[str], file_filter: FileFilter = None):
        self.monitored_path = Path(monitored_path)
        self.allowed_extensions = set(ext.lower() for ext in allowed_extensions)
        self.file_filter = file_filter or FileFilter.from_env()
    
    @staticmethod
    def calculate_hash(filename: str, size: int, mtime: float) -> str:
        """Вычисляет хэш из имени файла, размера и даты изменения"""
        hash_input = f"{filename}|{size}|{mtime}".encode('utf-8')
        return hashlib.sha256(hash_input).hexdigest()
    
    def scan(self) -> List[Dict]:
        """Сканирует папку и возвращает список файлов с метаданными (оптимизированная версия)"""
        files = []
        
        if not self.monitored_path.exists():
            return files
        
        # ОПТИМИЗАЦИЯ: используем os.walk вместо rglob для рекурсивного обхода
        # os.walk быстрее т.к. делает один stat вместо нескольких
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
                    # ОПТИМИЗАЦИЯ: один stat() вместо двух вызовов (is_file + stat)
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
                except (OSError, PermissionError):
                    # Пропускаем недоступные файлы
                    continue
        
        return files
    
    def count_files(self) -> int:
        """Быстрый подсчет файлов на диске (оптимизированная версия)"""
        count = 0
        if not self.monitored_path.exists():
            return count
        
        # ОПТИМИЗАЦИЯ: os.walk вместо rglob
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
