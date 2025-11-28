"""
FileManager - класс для управления файловыми операциями
Предоставляет утилиты для работы с файлами в контексте обработки документов
"""
import os
import hashlib
from pathlib import Path
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from pydantic import BaseModel

from utils.chunk_manager import ChunkManager
from utils.logging import get_logger

if TYPE_CHECKING:
    from utils.database import Database
    from utils.chunk_manager import Chunk

logger = get_logger(__name__)


class File(BaseModel):
    """Модель файла для работы с БД"""
    path: str
    hash: str
    raw_text: Optional[str] = None
    status_sync: str
    size: Optional[int] = None
    last_checked: Optional[datetime] = None
    mtime: Optional[float] = None



class FileManager:
    """Класс для файловых операций с интеграцией базы данных"""
    
    def __init__(self, database: 'Database'):
        """
        Args:
            database: Экземпляр Database для работы с БД
        """
        self.db = database
        self.chunk_manager = ChunkManager(database)
    
    def mark_as_processed(self, file: File) -> None:
        """
        Пометить файл как обрабатываемый (status_sync='processed')
        
        Args:
            file: Объект File
        """
        self.db.mark_as_processed(file.hash)
        logger.debug(f"Файл помечен как processed | hash={file.hash} path={file.path}")
    
    def mark_as_ok(self, file: File) -> None:
        """
        Пометить файл как успешно обработанный (status_sync='ok')
        
        Args:
            file: Объект File
        """
        self.db.mark_as_ok(file.hash)
        logger.info(f"✅ Файл успешно обработан | hash={file.hash} path={file.path}")
    
    def mark_as_error(self, file: File) -> None:
        """
        Пометить файл с ошибкой обработки (status_sync='error')
        
        Args:
            file: Объект File
        """
        self.db.mark_as_error(file.hash)
        logger.error(f"❌ Файл помечен как error | hash={file.hash} path={file.path}")
    
    def set_raw_text(self, file: File, raw_text: str) -> None:
        """
        Сохранить распарсенный текст файла в БД
        
        Args:
            file: Объект File
            raw_text: Распарсенный текст документа
        """
        self.db.set_raw_text(file.hash, raw_text)
        logger.debug(f"Сохранён raw_text | hash={file.hash} path={file.path} length={len(raw_text)}")
    
    def delete(self, file: File) -> None:
        """
        Удалить файл и все его чанки из БД
        
        Args:
            file: Объект File для удаления
        """
        # Сначала удаляем чанки
        deleted_chunks_count = self.chunk_manager.delete_chunks(file)
        # Затем удаляем запись о файле
        self.db.delete_file_by_hash(file.hash)
        logger.info(f"🗑️ Файл удалён | path={file.path} deleted_chunks={deleted_chunks_count}")
    
    def save_file_to_disk(self, file: File, temp_dir: str = "/home/alpaca/tmp_md") -> str:
        """
        Сохранить распарсенный текст на диск в формате Markdown
        
        Args:
            file: Объект File
            temp_dir: Директория для временных файлов (по умолчанию /home/alpaca/tmp_md)
            
        Returns:
            str: Полный путь к сохранённому файлу
        """
        import os
        
        temp_file_path = os.path.join(temp_dir, f"{file.path}.md")
        os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)
        
        with open(temp_file_path, "w", encoding="utf-8") as f:
            f.write(file.raw_text)
        
        logger.debug(f"💾 Распарсенный текст сохранён | path={temp_file_path} length={len(file.raw_text)}")
        return temp_file_path