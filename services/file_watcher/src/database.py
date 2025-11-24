import psycopg2
from contextlib import contextmanager
import os

class Database:
    def __init__(self, database_url: str = None, table_name: str = "files"):
        """
        Args:
            database_url: PostgreSQL connection string. Если не указан, берётся из DATABASE_URL env
            table_name: Название таблицы файлов
        """
        if database_url:
            self.connection_string = database_url
        else:
            self.connection_string = os.getenv('DATABASE_URL')
            
        if not self.connection_string:
            raise ValueError("DATABASE_URL not provided")
        
        self.table_name = table_name
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
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.table_name} (
                        id SERIAL PRIMARY KEY,
                        file_path TEXT NOT NULL UNIQUE,
                        file_size BIGINT NOT NULL,
                        file_hash TEXT,
                        file_mtime DOUBLE PRECISION,
                        status_sync TEXT DEFAULT 'ok',
                        last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cur.execute(f"CREATE INDEX IF NOT EXISTS idx_file_path ON {self.table_name}(file_path)")
                
                # Миграция: добавляем новые колонки если их нет
                cur.execute(f"""
                    DO $$ 
                    BEGIN 
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                      WHERE table_name='{self.table_name}' AND column_name='file_hash') THEN
                            ALTER TABLE {self.table_name} ADD COLUMN file_hash TEXT;
                        END IF;
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                      WHERE table_name='{self.table_name}' AND column_name='file_mtime') THEN
                            ALTER TABLE {self.table_name} ADD COLUMN file_mtime DOUBLE PRECISION;
                        END IF;
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                      WHERE table_name='{self.table_name}' AND column_name='status_sync') THEN
                            ALTER TABLE {self.table_name} ADD COLUMN status_sync TEXT DEFAULT 'ok';
                        END IF;
                    END $$;
                """)
                
                cur.execute(f"CREATE INDEX IF NOT EXISTS idx_file_hash ON {self.table_name}(file_hash)")
                cur.execute(f"CREATE INDEX IF NOT EXISTS idx_status_sync ON {self.table_name}(status_sync)")
    
    def reset_processed_to_ok(self) -> int:
        """Сбрасывает все статусы 'processed' на 'ok'
        
        Returns:
            int: Количество обновлённых записей
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"UPDATE {self.table_name} SET status_sync = 'ok' WHERE status_sync = 'processed'")
                return cur.rowcount
    
    def _decide_action_for_existing_file(self, current_status: str, hash_matches: bool) -> tuple:
        """Определяет действие для файла существующего в БД согласно таблице сценариев
        
        Args:
            current_status: Текущий статус файла в БД
            hash_matches: True если хэш на диске совпадает с хэшем в БД
            
        Returns:
            tuple: (action, new_status) где action = 'skip' | 'update_status' | 'update_full'
                   new_status - новый статус для файла (или None если skip)
        """
        # Строка 2 таблицы: Хэш совпадает (файл не изменился)
        if hash_matches:
            # Для всех статусов кроме NULL → ничего не делаем
            if current_status in ('added', 'updated', 'processed', 'deleted', 'ok', 'error'):
                return ('skip', None)
            # Для NULL → помечаем updated
            elif current_status is None:
                return ('update_status', 'updated')
        
        # Строка 3 таблицы: Хэш НЕ совпадает (файл изменился)
        else:
            # Для added и updated → обновляем хэш, меняем статус на updated
            if current_status in ('added', 'updated'):
                return ('update_full', 'updated')
            # Для всех остальных (processed, deleted, ok, error, NULL) → обновляем хэш, меняем на updated
            else:
                return ('update_full', 'updated')
        
        return ('skip', None)
    
    def sync_by_hash(self, disk_files: list) -> dict:
        """Синхронизирует БД с файлами на диске согласно документу "сценарии работы с файлами.md"
        
        Алгоритм:
        1. Если путь файла отсутствует в базе → добавляем запись со статусом 'added'
        2. Если путь есть в базе и на диске:
           - Хэш совпадает → применяем логику из строки 2 таблицы
           - Хэш не совпадает → применяем логику из строки 3 таблицы
        3. Если путь есть в базе но отсутствует на диске → помечаем 'deleted' (строка 1 таблицы)
        
        Args:
            disk_files: Список файлов с диска [{'path': str, 'size': int, 'hash': str, 'mtime': float}]
            
        Returns:
            dict: Статистика операций
                - added: количество добавленных файлов
                - updated: количество обновлённых файлов
                - unchanged: количество неизменённых файлов
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
                # Загружаем все записи из БД
                cur.execute(f"SELECT file_path, file_hash, status_sync FROM {self.table_name}")
                db_records = {row[0]: {'hash': row[1], 'status': row[2]} for row in cur.fetchall()}
                
                # Создаём словарь файлов с диска для быстрого поиска
                disk_paths = {f['path']: f for f in disk_files}
                
                from psycopg2.extras import execute_values
                
                # === ОБРАБОТКА ФАЙЛОВ С ДИСКА ===
                inserts = []  # Новые файлы для вставки
                status_updates = []  # Обновления только статуса
                full_updates = []  # Обновления хэша + метаданных + статуса
                
                for disk_path, disk_file in disk_paths.items():
                    # Сценарий 1: Путь файла отсутствует в базе
                    if disk_path not in db_records:
                        inserts.append((
                            disk_path,
                            disk_file['size'],
                            disk_file['hash'],
                            disk_file['mtime']
                        ))
                        stats['added'] += 1
                        continue
                    
                    # Сценарий 2-3: Путь есть в базе
                    db_record = db_records[disk_path]
                    hash_matches = (db_record['hash'] == disk_file['hash'])
                    
                    # Определяем действие согласно таблице сценариев
                    action, new_status = self._decide_action_for_existing_file(
                        current_status=db_record['status'],
                        hash_matches=hash_matches
                    )
                    
                    if action == 'skip':
                        # Файл не изменился (хэш совпадает)
                        stats['unchanged'] += 1
                        continue
                    elif action == 'update_status':
                        # Обновляем только статус (для NULL → updated при совпадении хэша)
                        status_updates.append((new_status, disk_path))
                        stats['updated'] += 1
                    elif action == 'update_full':
                        # Обновляем хэш, метаданные и статус (файл изменился)
                        full_updates.append((
                            disk_file['hash'],
                            disk_file['size'],
                            disk_file['mtime'],
                            new_status,
                            disk_path
                        ))
                        stats['updated'] += 1
                
                # === ПРИМЕНЕНИЕ ИЗМЕНЕНИЙ В БД ===
                
                # Вставка новых файлов
                if inserts:
                    execute_values(cur, f"""
                        INSERT INTO {self.table_name} 
                        (file_path, file_size, file_hash, file_mtime, last_checked, status_sync)
                        VALUES %s
                    """, inserts, template="(%s, %s, %s, %s, CURRENT_TIMESTAMP, 'added')", page_size=500)
                
                # Обновление только статусов
                if status_updates:
                    cur.executemany(f"""
                        UPDATE {self.table_name} 
                        SET status_sync = %s, last_checked = CURRENT_TIMESTAMP 
                        WHERE file_path = %s
                    """, status_updates)
                
                # Полное обновление (хэш + метаданные + статус)
                if full_updates:
                    cur.executemany(f"""
                        UPDATE {self.table_name} 
                        SET file_hash = %s, file_size = %s, file_mtime = %s, 
                            status_sync = %s, last_checked = CURRENT_TIMESTAMP
                        WHERE file_path = %s
                    """, full_updates)
                
                # === ОБРАБОТКА УДАЛЁННЫХ ФАЙЛОВ ===
                # Строка 1 таблицы: Файл есть в базе но отсутствует на диске
                missing_paths = set(db_records.keys()) - set(disk_paths.keys())
                if missing_paths:
                    # Помечаем как deleted ВСЕ отсутствующие файлы (кроме уже deleted)
                    paths_to_delete = [
                        path for path in missing_paths 
                        if db_records[path]['status'] != 'deleted'
                    ]
                    if paths_to_delete:
                        cur.execute(f"""
                            UPDATE {self.table_name} 
                            SET status_sync = 'deleted', last_checked = CURRENT_TIMESTAMP
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
                cur.execute(f"""
                    SELECT file_path, file_hash, status_sync
                    FROM {self.table_name}
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
                    f"UPDATE {self.table_name} SET status_sync = %s WHERE file_path = %s",
                    updates
                )
                return cur.rowcount
