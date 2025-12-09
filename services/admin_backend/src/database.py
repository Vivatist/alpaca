"""Database module для Admin Backend - мониторинг и статистика.

Этот модуль предоставляет специфичные для мониторинга методы, которые не входят
в domain/repository контракт. Admin Backend - это отдельный микросервис с собственными
нуждами (дашборды, статистика, health checks).

Почему изолирован от core/:
1. Admin Backend — независимый микросервис с собственной кодовой базой
2. Ему нужна только статистика, агрегации, health checks
3. Не зависит от доменной логики Worker'а

Модуль содержит собственную реализацию подключения к PostgreSQL.
"""

from contextlib import contextmanager
from typing import Dict, List, Optional, Any
import os

import psycopg2
from psycopg2.pool import ThreadedConnectionPool


class Database:
    """Фасад для мониторинговых запросов Admin Backend.
    
    Содержит собственную реализацию подключения к PostgreSQL
    и предоставляет методы для dashboard/monitoring.
    """

    def __init__(self):
        self._database_url = os.getenv("DATABASE_URL")
        if not self._database_url:
            raise ValueError("DATABASE_URL не установлен")
        
        # Пул соединений для многопоточности
        self._pool: Optional[ThreadedConnectionPool] = None
    
    def _get_pool(self) -> ThreadedConnectionPool:
        """Ленивая инициализация пула соединений."""
        if self._pool is None:
            self._pool = ThreadedConnectionPool(
                minconn=1,
                maxconn=5,
                dsn=self._database_url
            )
        return self._pool

    @contextmanager
    def get_connection(self):
        """Контекстный менеджер для получения соединения из пула."""
        pool = self._get_pool()
        conn = pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            pool.putconn(conn)
    
    def get_file_state_stats(self) -> Dict[str, int]:
        """Получает статистику по файлам в таблице files
        
        Returns:
            Dict с количеством файлов по каждому статусу:
            {
                'total': 1000,
                'ok': 950,
                'added': 30,
                'updated': 10,
                'processed': 5,
                'deleted': 3,
                'error': 2
            }
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Получаем распределение по статусам
                cur.execute("""
                    SELECT 
                        status_sync,
                        COUNT(*) as count
                    FROM files
                    GROUP BY status_sync
                    ORDER BY status_sync
                """)
                
                stats = {'total': 0}
                for row in cur.fetchall():
                    status = row[0] if row[0] else 'unknown'
                    count = row[1]
                    stats[status] = count
                    stats['total'] += count
                
                # Добавляем нулевые значения для отсутствующих статусов
                for status in ['ok', 'added', 'updated', 'processed', 'deleted', 'error']:
                    if status not in stats:
                        stats[status] = 0
                
                return stats
    
    def get_documents_stats(self) -> Dict[str, Any]:
        """Получает статистику по таблице chunks
        
        Returns:
            Dict со статистикой:
            {
                'total_chunks': 5000,
                'unique_files': 950,
                'avg_chunks_per_file': 5.26
            }
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Общее количество чанков
                cur.execute("SELECT COUNT(*) FROM chunks")
                total_chunks = cur.fetchone()[0]
                
                # Количество уникальных файлов
                cur.execute("""
                    SELECT COUNT(DISTINCT metadata->>'file_hash') 
                    FROM chunks 
                    WHERE metadata->>'file_hash' IS NOT NULL
                """)
                unique_files = cur.fetchone()[0]
                
                # Средний размер
                avg_chunks = round(total_chunks / unique_files, 2) if unique_files > 0 else 0
                
                return {
                    'total_chunks': total_chunks,
                    'unique_files': unique_files,
                    'avg_chunks_per_file': avg_chunks
                }
    
    def get_file_state_details(
        self, 
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Получает детальную информацию о файлах
        
        Args:
            status: Фильтр по статусу (optional)
            limit: Максимальное количество записей
            offset: Смещение для пагинации
            
        Returns:
            List словарей с информацией о файлах
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                query = """
                    SELECT 
                        path,
                        size,
                        hash,
                        status_sync,
                        mtime,
                        last_checked
                    FROM files
                """
                
                params = []
                if status:
                    query += " WHERE status_sync = %s"
                    params.append(status)
                
                query += " ORDER BY last_checked DESC LIMIT %s OFFSET %s"
                params.extend([limit, offset])
                
                cur.execute(query, params)
                
                results = []
                for row in cur.fetchall():
                    results.append({
                        'file_path': row[0],
                        'file_size': row[1],
                        'file_hash': row[2],
                        'status_sync': row[3],
                        'file_mtime': row[4],
                        'last_checked': row[5].isoformat() if row[5] else None
                    })
                
                return results
    
    def get_processing_queue(self) -> Dict[str, List[Dict[str, Any]]]:
        """Получает текущую очередь на обработку
        
        Returns:
            Dict с файлами по типу действия:
            {
                'added': [...],
                'updated': [...],
                'deleted': [...]
            }
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        path,
                        hash,
                        size,
                        status_sync
                    FROM files
                    WHERE status_sync IN ('added', 'updated', 'deleted')
                    ORDER BY status_sync, path
                    LIMIT 1000
                """)
                
                queue = {
                    'added': [],
                    'updated': [],
                    'deleted': []
                }
                
                for row in cur.fetchall():
                    item = {
                        'file_path': row[0],
                        'file_hash': row[1],
                        'file_size': row[2],
                        'status_sync': row[3]
                    }
                    
                    if row[3] in queue:
                        queue[row[3]].append(item)
                
                return queue
    
    def get_error_files(self) -> List[Dict[str, Any]]:
        """Получает список файлов со статусом error
        
        Returns:
            List файлов с ошибками
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        path,
                        hash,
                        size,
                        last_checked
                    FROM files
                    WHERE status_sync = 'error'
                    ORDER BY last_checked DESC
                """)
                
                results = []
                for row in cur.fetchall():
                    results.append({
                        'file_path': row[0],
                        'file_hash': row[1],
                        'file_size': row[2],
                        'last_checked': row[3].isoformat() if row[3] else None
                    })
                
                return results
    
    def get_database_health(self) -> Dict[str, Any]:
        """Проверяет состояние базы данных
        
        Returns:
            Dict со статусом БД и дополнительной информацией
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Проверка подключения
                    cur.execute("SELECT 1")
                    
                    # Проверка pgvector
                    cur.execute("""
                        SELECT extname, extversion 
                        FROM pg_extension 
                        WHERE extname = 'vector'
                    """)
                    pgvector = cur.fetchone()
                    
                    # Размер таблиц (используем правильные имена таблиц)
                    cur.execute("""
                        SELECT 
                            pg_size_pretty(pg_total_relation_size('files')) as file_state_size,
                            pg_size_pretty(pg_total_relation_size('chunks')) as documents_size
                    """)
                    sizes = cur.fetchone()
                    
                    return {
                        'status': 'healthy',
                        'connected': True,
                        'pgvector_version': pgvector[1] if pgvector else None,
                        'table_sizes': {
                            'files': sizes[0] if sizes else 'unknown',
                            'chunks': sizes[1] if sizes else 'unknown'
                        }
                    }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'connected': False,
                'error': str(e)
            }
