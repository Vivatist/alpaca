"""
ChunkManager - класс для управления чанками документов
Отвечает за операции с чанками в базе данных и их обработку
"""
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from pydantic import BaseModel

from utils.logging import get_logger

if TYPE_CHECKING:
    from alpaca.domain.files.repository import Database
    from alpaca.domain.files.models import FileSnapshot

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
    
    def delete_chunks(self, file: 'FileSnapshot') -> int:
        """
        Удалить все чанки файла из БД
        
        Args:
            file: Объект File, чанки которого нужно удалить
            
        Returns:
            Количество удалённых чанков
        """
        deleted_by_hash = self.db.delete_chunks_by_hash(file.hash)
        deleted_total = deleted_by_hash

        # Дополнительная гарантия: удаляем все чанки по пути (важно для updated файлов с новым хэшем)
        deleted_by_path = self.db.delete_chunks_by_path(file.path)
        if deleted_by_path:
            deleted_total += deleted_by_path
            logger.debug(
                "Удалены остаточные чанки по пути | path=%s hash=%s fallback=%s",
                file.path,
                file.hash,
                deleted_by_path,
            )
        else:
            logger.debug(
                "Чанки удалены по хэшу | path=%s hash=%s count=%s",
                file.path,
                file.hash,
                deleted_by_hash,
            )

        return deleted_total
    
    def get_chunks_count(self, file: 'FileSnapshot') -> int:
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
    
    def get_chunks(self, file: 'FileSnapshot') -> List[Chunk]:
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
