import psycopg2
from contextlib import contextmanager
import os

class Database:
    def __init__(self, database_url: str = None):
        """
        Args:
            database_url: PostgreSQL connection string. Если не указан, берётся из DATABASE_URL env
        """
        if database_url:
            self.connection_string = database_url
        else:
            self.connection_string = os.getenv('DATABASE_URL')
            
        if not self.connection_string:
            raise ValueError("DATABASE_URL not provided")
        
        self._init_tables()
    
    @contextmanager
    def get_connection(self):
        conn = psycopg2.connect(self.connection_string)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _init_tables(self):
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS file_state (
                        id SERIAL PRIMARY KEY,
                        file_path TEXT NOT NULL UNIQUE,
                        file_size BIGINT NOT NULL,
                        file_hash TEXT,
                        file_mtime DOUBLE PRECISION,
                        status_sync TEXT DEFAULT 'ok',
                        last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cur.execute("CREATE INDEX IF NOT EXISTS idx_file_path ON file_state(file_path)")
                
                # Миграция: добавляем новые колонки если их нет
                cur.execute("""
                    DO $$ 
                    BEGIN 
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                      WHERE table_name='file_state' AND column_name='file_hash') THEN
                            ALTER TABLE file_state ADD COLUMN file_hash TEXT;
                        END IF;
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                      WHERE table_name='file_state' AND column_name='file_mtime') THEN
                            ALTER TABLE file_state ADD COLUMN file_mtime DOUBLE PRECISION;
                        END IF;
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                      WHERE table_name='file_state' AND column_name='status_sync') THEN
                            ALTER TABLE file_state ADD COLUMN status_sync TEXT DEFAULT 'ok';
                        END IF;
                    END $$;
                """)
                
                cur.execute("CREATE INDEX IF NOT EXISTS idx_file_hash ON file_state(file_hash)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_status_sync ON file_state(status_sync)")
    
    def reset_processed_to_ok(self) -> int:
        """Сбрасывает все статусы 'processed' на 'ok'
        
        Returns:
            int: Количество обновлённых записей
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE file_state SET status_sync = 'ok' WHERE status_sync = 'processed'")
                return cur.rowcount
    
    def sync_by_hash(self, disk_files: list) -> dict:
        """Синхронизирует file_state с диском используя хэши как источник истины
        
        ВАЖНО: НЕ удаляет записи из БД. Только добавляет/обновляет файлы с диска.
        Файлы, удалённые с диска, помечаются status_sync='deleted'.
        
        Returns:
            dict: Статистика операций
                - added: количество добавленных
                - updated: количество обновлённых
                - unchanged: количество неизменённых
                - deleted: количество помеченных как удалённые
        """
        stats = {
            'added': 0,
            'updated': 0,
            'unchanged': 0,
            'deleted': 0
        }
        
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Получаем все хэши и пути из БД
                cur.execute("SELECT file_hash, file_path FROM file_state")
                db_records = cur.fetchall()
                db_hashes = {row[0]: row[1] for row in db_records}  # hash -> path
                db_paths = {row[1]: row[0] for row in db_records}  # path -> hash
                
                # Создаём множество хэшей и путей с диска
                disk_hashes = {f['hash']: f for f in disk_files}
                disk_paths = {f['path'] for f in disk_files}
                
                # Классифицируем файлы
                from psycopg2.extras import execute_values
                
                for disk_hash, disk_file in disk_hashes.items():
                    if disk_hash in db_hashes:
                        # Хэш существует - файл не изменился
                        stats['unchanged'] += 1
                    else:
                        # Новый хэш - проверяем, есть ли файл с таким путём в БД
                        if disk_file['path'] in db_paths:
                            # Путь есть, но хэш другой = файл изменился
                            stats['updated'] += 1
                        else:
                            # Ни пути, ни хэша нет = новый файл
                            stats['added'] += 1
                
                # Батчинг всех операций вставки/обновления для файлов с диска
                if disk_files:
                    values = [(f['path'], f['size'], f['hash'], f['mtime']) for f in disk_files]
                    execute_values(cur, """
                        INSERT INTO file_state (file_path, file_size, file_hash, file_mtime, last_checked, status_sync)
                        VALUES %s
                        ON CONFLICT (file_path) DO UPDATE SET
                            file_size = CASE 
                                WHEN file_state.status_sync = 'processed' THEN file_state.file_size
                                WHEN file_state.status_sync = 'error' THEN file_state.file_size
                                ELSE EXCLUDED.file_size
                            END,
                            file_hash = CASE 
                                WHEN file_state.status_sync = 'processed' THEN file_state.file_hash
                                WHEN file_state.status_sync = 'error' THEN file_state.file_hash
                                ELSE EXCLUDED.file_hash
                            END,
                            file_mtime = CASE 
                                WHEN file_state.status_sync = 'processed' THEN file_state.file_mtime
                                WHEN file_state.status_sync = 'error' THEN file_state.file_mtime
                                ELSE EXCLUDED.file_mtime
                            END,
                            last_checked = CURRENT_TIMESTAMP,
                            status_sync = CASE 
                                WHEN file_state.status_sync = 'error' THEN 'error'
                                WHEN file_state.status_sync = 'processed' THEN 'processed'
                                WHEN file_state.status_sync = 'deleted' THEN 'updated'
                                WHEN file_state.file_hash != EXCLUDED.file_hash THEN 'updated'
                                ELSE file_state.status_sync
                            END
                    """, values, template="(%s, %s, %s, %s, CURRENT_TIMESTAMP, 'added')", page_size=500)
                
                # Помечаем файлы, которых нет на диске, как deleted
                missing_paths = set(db_paths.keys()) - disk_paths
                if missing_paths:
                    cur.execute("""
                        UPDATE file_state 
                        SET status_sync = 'deleted', 
                            last_checked = CURRENT_TIMESTAMP
                        WHERE file_path = ANY(%s)
                          AND status_sync != 'deleted'
                          AND status_sync != 'error'
                    """, (list(missing_paths),))
                    stats['deleted'] = cur.rowcount
        
        return stats
    
    def get_file_state_records(self) -> list:
        """Получает все записи из file_state
        
        Returns:
            list: [(file_path, file_hash, status_sync), ...]
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT file_path, file_hash, status_sync
                    FROM file_state
                """)
                return cur.fetchall()
    
    def get_documents_records(self) -> list:
        """Получает все уникальные файлы из chunks (группируя чанки)
        
        Returns:
            list: [(file_hash, file_path, num_chunks), ...]
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        metadata->>'file_hash' as file_hash,
                        metadata->>'file_path' as file_path,
                        COUNT(*) as num_chunks
                    FROM chunks 
                    WHERE metadata->>'file_hash' IS NOT NULL
                      AND metadata->>'file_path' IS NOT NULL
                    GROUP BY metadata->>'file_hash', metadata->>'file_path'
                """)
                return cur.fetchall()
    
    def update_status_sync_batch(self, updates: list) -> int:
        """Массовое обновление status_sync для файлов
        
        Args:
            updates: Список кортежей [(new_status, file_path), ...]
        
        Returns:
            int: Количество обновлённых записей
        """
        if not updates:
            return 0
        
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    "UPDATE file_state SET status_sync = %s WHERE file_path = %s",
                    updates
                )
                return cur.rowcount
