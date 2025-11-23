"""Database module для FileStatusProcessor

Отвечает за:
- Получение файлов с определёнными статусами (added, updated, deleted)
- Обновление статусов после обработки
- Работа с таблицами files и chunks
"""

import psycopg2
from contextlib import contextmanager
from typing import Dict, List, Tuple
from app.utils.logging import get_logger

logger = get_logger(__name__)


class Database:
    """Класс для работы с БД в контексте обработки изменений файлов"""
    
    def __init__(self, database_url: str):
        """
        Args:
            database_url: PostgreSQL connection string
        """
        if not database_url:
            raise ValueError("database_url is required")
        
        self.connection_string = database_url
    
    @contextmanager
    def get_connection(self):
        """Контекстный менеджер для подключения к БД"""
        conn = psycopg2.connect(self.connection_string)
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()
    
    def get_processed_count(self) -> int:
        """Получает количество файлов в статусе 'processed'
        
        Returns:
            int: Количество файлов в обработке
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*)
                    FROM files
                    WHERE status_sync = 'processed'
                """)
                return cur.fetchone()[0]
    
    def get_pending_files(self) -> Dict[str, List[Tuple[str, str, int]]]:
        """Получает файлы, требующие обработки (status_sync in ['added', 'updated', 'deleted'])
        
        Returns:
            dict: Словарь с файлами по статусам
                {
                    'added': [(file_path, file_hash, file_size), ...],
                    'updated': [(file_path, file_hash, file_size), ...],
                    'deleted': [(file_path, file_hash, file_size), ...]
                }
        """
        result = {
            'added': [],
            'updated': [],
            'deleted': []
        }
        
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT file_path, file_hash, file_size, status_sync
                    FROM files
                    WHERE status_sync IN ('added', 'updated', 'deleted')
                    ORDER BY file_mtime DESC
                """)
                
                rows = cur.fetchall()
                
                for row in rows:
                    file_path, file_hash, file_size, status = row
                    file_info = (file_path, file_hash, file_size)
                    
                    if status == 'added':
                        result['added'].append(file_info)
                    elif status == 'updated':
                        result['updated'].append(file_info)
                    elif status == 'deleted':
                        result['deleted'].append(file_info)
        
        return result
    
    def mark_as_processed(self, file_hash: str) -> bool:
        """Помечает файл как обработанный (status_sync = 'processed')
        
        Используется для added и updated файлов после успешного запуска обработки.
        
        Args:
            file_hash: SHA256 хэш файла
        
        Returns:
            bool: True если обновление успешно
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE files
                        SET status_sync = 'processed',
                            last_checked = CURRENT_TIMESTAMP
                        WHERE file_hash = %s
                    """, (file_hash,))
                    return cur.rowcount > 0
        except Exception as e:
            logger.error(f"Error marking hash {file_hash} as processed: {e}")
            return False
    
    def mark_as_ok(self, file_hash: str) -> bool:
        """Помечает файл как успешно обработанный (status_sync = 'ok')
        
        Вызывается после завершения обработки документа (когда chunks добавлены в БД).
        
        Args:
            file_hash: SHA256 хэш файла
        
        Returns:
            bool: True если обновление успешно
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE files
                        SET status_sync = 'ok',
                            last_checked = CURRENT_TIMESTAMP
                        WHERE file_hash = %s
                    """, (file_hash,))
                    return cur.rowcount > 0
        except Exception as e:
            logger.error(f"Error marking hash {file_hash} as ok: {e}")
            return False
    
    def mark_as_error(self, file_hash: str) -> bool:
        """Помечает файл как ошибочный (status_sync = 'error')
        
        Args:
            file_hash: SHA256 хэш файла
        
        Returns:
            bool: True если обновление успешно
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE files
                        SET status_sync = 'error',
                            last_checked = CURRENT_TIMESTAMP
                        WHERE file_hash = %s
                    """, (file_hash,))
                    return cur.rowcount > 0
        except Exception as e:
            logger.error(f"Error marking hash {file_hash} as error: {e}")
            return False
    
    def delete_file_by_hash(self, file_hash: str) -> bool:
        """Удаляет запись файла из files по хэшу
        
        Args:
            file_hash: SHA256 хэш файла
        
        Returns:
            bool: True если удаление успешно
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        DELETE FROM files
                        WHERE file_hash = %s
                    """, (file_hash,))
                    return cur.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting file for hash {file_hash}: {e}")
            return False
    
    def delete_chunks_by_hash(self, file_hash: str) -> int:
        """Удаляет все чанки документа из таблицы chunks по хэшу
        
        Args:
            file_hash: SHA256 хэш файла
        
        Returns:
            int: Количество удалённых чанков
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        DELETE FROM chunks
                        WHERE metadata->>'file_hash' = %s
                    """, (file_hash,))
                    return cur.rowcount
        except Exception as e:
            logger.error(f"Error deleting chunks for hash {file_hash}: {e}")
            return 0
    
    def delete_chunks_by_path(self, file_path: str) -> int:
        """Удаляет все чанки документа из таблицы chunks по пути файла
        
        Используется для updated файлов, когда хэш уже изменился в files,
        но старые чанки всё ещё хранятся под старым хэшом.
        
        Args:
            file_path: Путь к файлу
        
        Returns:
            int: Количество удалённых чанков
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        DELETE FROM chunks
                        WHERE metadata->>'file_path' = %s
                    """, (file_path,))
                    return cur.rowcount
        except Exception as e:
            logger.error(f"Error deleting chunks for path {file_path}: {e}")
            return 0
