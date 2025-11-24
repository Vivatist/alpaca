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
                    CREATE TABLE IF NOT EXISTS files (
                        id SERIAL PRIMARY KEY,
                        file_path TEXT NOT NULL UNIQUE,
                        file_size BIGINT NOT NULL,
                        file_hash TEXT,
                        file_mtime DOUBLE PRECISION,
                        status_sync TEXT DEFAULT 'ok',
                        last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cur.execute("CREATE INDEX IF NOT EXISTS idx_file_path ON files(file_path)")
                
                # Миграция: добавляем новые колонки если их нет
                cur.execute("""
                    DO $$ 
                    BEGIN 
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                      WHERE table_name='files' AND column_name='file_hash') THEN
                            ALTER TABLE files ADD COLUMN file_hash TEXT;
                        END IF;
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                      WHERE table_name='files' AND column_name='file_mtime') THEN
                            ALTER TABLE files ADD COLUMN file_mtime DOUBLE PRECISION;
                        END IF;
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                      WHERE table_name='files' AND column_name='status_sync') THEN
                            ALTER TABLE files ADD COLUMN status_sync TEXT DEFAULT 'ok';
                        END IF;
                    END $$;
                """)
                
                cur.execute("CREATE INDEX IF NOT EXISTS idx_file_hash ON files(file_hash)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_status_sync ON files(status_sync)")
    
    def reset_processed_to_ok(self) -> int:
        """Сбрасывает все статусы 'processed' на 'ok'
        
        Returns:
            int: Количество обновлённых записей
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE files SET status_sync = 'ok' WHERE status_sync = 'processed'")
                return cur.rowcount
    
    def sync_by_hash(self, disk_files: list) -> dict:
        """Синхронизирует files с диском (файлы на диске - источник истины)
        
        Логика:
        1. Проходит по файлам с диска
        2.1 Путь есть на диске, нет в таблице → добавляем со статусом 'added'
        2.2 Путь есть на диске и в таблице, хэш совпадает → статус 'ok'
        2.3 Путь есть на диске и в таблице, хэш различается → статус 'updated'
        2.4 Путь есть в таблице, но отсутствует на диске → статус 'deleted'
        3. Пропускаем записи со статусами 'error' или 'processed'
        
        Returns:
            dict: Статистика операций
                - added: количество добавленных
                - updated: количество обновлённых
                - unchanged: количество неизменённых (ok)
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
                # Получаем все записи из БД с их статусами
                cur.execute("SELECT file_path, file_hash, status_sync FROM files")
                db_records = {row[0]: {'hash': row[1], 'status': row[2]} for row in cur.fetchall()}
                
                # Создаём множество путей с диска
                disk_paths = {f['path']: f for f in disk_files}
                
                from psycopg2.extras import execute_values
                
                # Обрабатываем файлы с диска
                inserts = []
                updates = []
                
                for disk_path, disk_file in disk_paths.items():
                    if disk_path in db_records:
                        db_record = db_records[disk_path]
                        
                        # Пропускаем файлы в обработке или с ошибками
                        if db_record['status'] in ('error', 'processed'):
                            continue
                        
                        if db_record['hash'] == disk_file['hash']:
                            # Хэш совпадает
                            # Если файл в added/updated - не трогаем, он ждет обработки
                            if db_record['status'] in ('added', 'updated'):
                                continue
                            # Иначе переводим в ok (для deleted или других статусов)
                            if db_record['status'] != 'ok':
                                updates.append(('ok', disk_path))
                                stats['unchanged'] += 1
                        else:
                            # Хэш различается → updated (даже если был added)
                            updates.append(('updated', disk_path))
                            # Обновляем также хэш и метаданные
                            cur.execute("""
                                UPDATE files 
                                SET file_hash = %s, file_size = %s, file_mtime = %s,
                                    status_sync = 'updated', last_checked = CURRENT_TIMESTAMP
                                WHERE file_path = %s
                            """, (disk_file['hash'], disk_file['size'], disk_file['mtime'], disk_path))
                            stats['updated'] += 1
                    else:
                        # Файла нет в БД → added
                        inserts.append((disk_path, disk_file['size'], disk_file['hash'], disk_file['mtime']))
                        stats['added'] += 1
                
                # Массовая вставка новых файлов
                if inserts:
                    execute_values(cur, """
                        INSERT INTO files (file_path, file_size, file_hash, file_mtime, last_checked, status_sync)
                        VALUES %s
                    """, inserts, template="(%s, %s, %s, %s, CURRENT_TIMESTAMP, 'added')", page_size=500)
                
                # Массовое обновление статусов на 'ok'
                if updates:
                    cur.executemany("UPDATE files SET status_sync = %s, last_checked = CURRENT_TIMESTAMP WHERE file_path = %s", updates)
                
                # Помечаем файлы, которых нет на диске, как deleted
                missing_paths = set(db_records.keys()) - set(disk_paths.keys())
                if missing_paths:
                    # Помечаем все отсутствующие файлы как deleted (включая error, processed)
                    # Пропускаем только уже помеченные как deleted
                    paths_to_delete = [
                        path for path in missing_paths 
                        if db_records[path]['status'] != 'deleted'
                    ]
                    if paths_to_delete:
                        cur.execute("""
                            UPDATE files 
                            SET status_sync = 'deleted', 
                                last_checked = CURRENT_TIMESTAMP
                            WHERE file_path = ANY(%s)
                        """, (paths_to_delete,))
                        stats['deleted'] = cur.rowcount
        
        return stats
    
    def get_file_state_records(self) -> list:
        """Получает все записи из files
        
        Returns:
            list: [(file_path, file_hash, status_sync), ...]
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT file_path, file_hash, status_sync
                    FROM files
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
                    "UPDATE files SET status_sync = %s WHERE file_path = %s",
                    updates
                )
                return cur.rowcount
