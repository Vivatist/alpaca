"""
ChunkManager - класс для управления чанками документов
Отвечает за операции с чанками в базе данных и их обработку
"""
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from pydantic import BaseModel

from utils.logging import get_logger

if TYPE_CHECKING:
    from utils.database import Database
    from utils.file_manager import File

logger = get_logger(__name__)


class Chunk(BaseModel):
    """Модель чанка для работы с БД"""
    content: str
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None



class ChunkManager:
    """Класс для операций с чанками документов"""
    
    def __init__(self, database: 'Database'):
        """
        Args:
            database: Экземпляр Database для работы с БД
        """
        self.db = database
    
    def delete_chunks(self, file: 'File') -> int:
        """
        Удалить все чанки файла из БД
        
        Args:
            file: Объект File, чанки которого нужно удалить
            
        Returns:
            Количество удалённых чанков
        """
        deleted_count = self.db.delete_chunks_by_hash(file.hash)
        logger.debug(f"Чанки удалены | path={file.path} count={deleted_count}")
        return deleted_count
    
    def get_chunks_count(self, file: 'File') -> int:
        """
        Получить количество чанков файла
        
        Args:
            file: Объект File
            
        Returns:
            Количество чанков в БД
        """
        count = self.db.get_chunks_count(file.hash)
        logger.debug(f"Количество чанков | hash={file.hash} count={count}")
        return count
    
    def save(self, chunk: Chunk) -> None:
        """
        Сохранить чанк в БД
        
        Args:
            chunk: Объект Chunk для сохранения
        """
        self.db.save_chunk(chunk.content, chunk.metadata, chunk.embedding)
        file_hash = chunk.metadata.get('file_hash', 'unknown')
        logger.debug(f"Чанк сохранён | hash={file_hash} content_length={len(chunk.content)}")
    
    def get_chunks(self, file: 'File') -> List[Chunk]:
        """
        Получить все чанки файла из БД
        
        Args:
            file: Объект File
            
        Returns:
            Список объектов Chunk
        """
        rows = self.db.get_chunks_by_hash(file.hash)
        chunks = [
            Chunk(
                content=row[0],
                metadata=row[1],
                embedding=row[2] if len(row) > 2 else None
            )
            for row in rows
        ]
        logger.debug(f"Получены чанки | hash={file.hash} count={len(chunks)}")
        return chunks
