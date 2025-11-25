"""
Тесты для sync_by_hash согласно документу "сценарии работы с файлами.md"

Тестируем все ячейки таблицы сценариев:
- Строка 1: Файл удалён (есть в БД, нет на диске)
- Строка 2: Хэш совпадает (файл не изменился)
- Строка 3: Хэш не совпадает (файл изменился)

Для каждой строки тестируем все статусы: added, updated, processed, deleted, ok, error, NULL
"""
import os
import sys
import tempfile
import shutil
from pathlib import Path

# Добавляем src/ в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils.database import PostgreDatabase
from scanner import Scanner


class TestSyncLogic:
    """Тесты синхронизации согласно таблице сценариев"""
    
    def __init__(self, database_url: str):
        self.db = PostgreDatabase(database_url, table_name='test_files')
        self.test_dir = tempfile.mkdtemp(prefix='filewatcher_test_')
        
        # Создаём file_filter без ограничений для тестов
        from file_filter import FileFilter
        test_filter = FileFilter(min_size=0, max_size=100*1024*1024, excluded_dirs=[], excluded_patterns=[])
        
        self.scanner = Scanner(
            monitored_path=self.test_dir,
            allowed_extensions=['.txt'],
            file_filter=test_filter
        )
        
    def cleanup(self):
        """Очистка тестовых данных"""
        shutil.rmtree(self.test_dir, ignore_errors=True)
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"DROP TABLE IF EXISTS {self.db.table_name}")
    
    def _create_file(self, filename: str, content: str = "test content") -> dict:
        """Создаёт тестовый файл и возвращает его метаданные"""
        file_path = Path(self.test_dir) / filename
        file_path.write_text(content * 20)  # 20 повторений для размера > 100 байт
        
        # Получаем метаданные через scanner
        files = self.scanner.scan()
        for f in files:
            if f['path'] == filename:
                return f
        raise ValueError(f"File {filename} not found after creation")
    
    def _insert_record(self, path: str, file_hash: str, status: str, size: int = 100):
        """Вставляет запись в БД с заданным статусом"""
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                if status is None:
                    # NULL статус
                    cur.execute(f"""
                        INSERT INTO {self.db.table_name} 
                        (file_path, file_size, file_hash, file_mtime, status_sync)
                        VALUES (%s, %s, %s, %s, NULL)
                    """, (path, size, file_hash, 1234567890.0))
                else:
                    cur.execute(f"""
                        INSERT INTO {self.db.table_name} 
                        (file_path, file_size, file_hash, file_mtime, status_sync)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (path, size, file_hash, 1234567890.0, status))
    
    def _get_status(self, path: str) -> str:
        """Получает текущий статус файла из БД"""
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT status_sync FROM {self.db.table_name} WHERE file_path = %s", (path,))
                row = cur.fetchone()
                return row[0] if row else None
    
    def _get_hash(self, path: str) -> str:
        """Получает текущий хэш файла из БД"""
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT file_hash FROM {self.db.table_name} WHERE file_path = %s", (path,))
                row = cur.fetchone()
                return row[0] if row else None
    
    # ========== СТРОКА 1: ФАЙЛ УДАЛЁН (есть в БД, нет на диске) ==========
    
    def test_row1_deleted_file_status_added(self):
        """Строка 1, колонка added: файл удалён → пометить как deleted"""
        print("\n🧪 Тест: Удалённый файл со статусом 'added'")
        
        # Вставляем запись с статусом added
        self._insert_record('deleted_added.txt', 'hash123', 'added')
        
        # Синхронизируем (файла нет на диске)
        stats = self.db.sync_by_hash([])
        
        # Проверяем: статус должен стать deleted
        assert self._get_status('deleted_added.txt') == 'deleted', "Статус должен быть 'deleted'"
        assert stats['deleted'] == 1, "Должен быть 1 удалённый файл"
        print("✅ Passed: added → deleted")
    
    def test_row1_deleted_file_all_statuses(self):
        """Строка 1: тест всех статусов при удалении файла"""
        print("\n🧪 Тест: Удалённый файл - все статусы")
        
        statuses = ['added', 'updated', 'processed', 'deleted', 'ok', 'error', None]
        
        for status in statuses:
            status_str = 'NULL' if status is None else status
            filename = f'del_{status_str}.txt'
            
            self._insert_record(filename, 'hash_' + status_str, status)
            
        # Синхронизируем с пустым диском
        stats = self.db.sync_by_hash([])
        
        # Проверяем: все кроме уже deleted должны стать deleted
        for status in statuses:
            status_str = 'NULL' if status is None else status
            filename = f'del_{status_str}.txt'
            current_status = self._get_status(filename)
            
            if status == 'deleted':
                # Уже deleted → не меняется
                assert current_status == 'deleted', f"{filename}: должен остаться deleted"
            else:
                # Все остальные → deleted
                assert current_status == 'deleted', f"{filename}: должен стать deleted"
        
        # Проверяем статистику: 6 файлов (7 - 1 уже deleted)
        assert stats['deleted'] == 6, "Должно быть 6 помеченных как deleted"
        print("✅ Passed: Все статусы → deleted (кроме уже deleted)")
    
    # ========== СТРОКА 2: ХЭШ СОВПАДАЕТ (файл не изменился) ==========
    
    def test_row2_hash_matches_added(self):
        """Строка 2, колонка added: хэш совпадает → ничего не делаем"""
        print("\n🧪 Тест: Неизменённый файл со статусом 'added'")
        
        # Создаём файл
        file_meta = self._create_file('unchanged_added.txt', 'content1')
        
        # Вставляем с тем же хэшем и статусом added
        self._insert_record(file_meta['path'], file_meta['hash'], 'added', file_meta['size'])
        
        # Синхронизируем
        stats = self.db.sync_by_hash([file_meta])
        
        # Проверяем: статус должен остаться added
        assert self._get_status(file_meta['path']) == 'added', "Статус должен остаться 'added'"
        assert stats['added'] == 0 and stats['updated'] == 0, "Не должно быть изменений"
        print("✅ Passed: added + hash_match → не меняется")
    
    def test_row2_hash_matches_all_statuses(self):
        """Строка 2: тест всех статусов при совпадении хэша"""
        print("\n🧪 Тест: Неизменённый файл - все статусы")
        
        test_cases = [
            ('added', 'added'),       # added → added (не меняется)
            ('updated', 'updated'),   # updated → updated (не меняется)
            ('processed', 'processed'), # processed → processed (не меняется)
            ('deleted', 'updated'),   # deleted → updated (файл вернулся!)
            ('ok', 'ok'),             # ok → ok (не меняется)
            ('error', 'error'),       # error → error (не меняется)
            (None, 'updated'),        # NULL → updated (меняется!)
        ]
        
        disk_files = []
        
        for initial_status, expected_status in test_cases:
            status_str = 'NULL' if initial_status is None else initial_status
            filename = f'unchanged_{status_str}.txt'
            
            # Создаём файл
            file_meta = self._create_file(filename, f'content_{status_str}')
            disk_files.append(file_meta)
            
            # Вставляем с тем же хэшем
            self._insert_record(file_meta['path'], file_meta['hash'], initial_status, file_meta['size'])
        
        # Синхронизируем
        stats = self.db.sync_by_hash(disk_files)
        
        # Проверяем результаты
        for initial_status, expected_status in test_cases:
            status_str = 'NULL' if initial_status is None else initial_status
            filename = f'unchanged_{status_str}.txt'
            current_status = self._get_status(filename)
            
            assert current_status == expected_status, \
                f"{filename}: ожидали {expected_status}, получили {current_status}"
        
        # 5 файлов не изменились (skip), 2 файла обновились (NULL и deleted)
        assert stats['unchanged'] == 5, "5 файлов должны быть unchanged (все кроме NULL и deleted)"
        assert stats['updated'] == 2, "2 файла (NULL и deleted) должны быть updated"
        print("✅ Passed: Хэш совпадает - статусы не меняются (кроме NULL → updated)")
    
    # ========== СТРОКА 3: ХЭШ НЕ СОВПАДАЕТ (файл изменился) ==========
    
    def test_row3_hash_differs_added(self):
        """Строка 3, колонка added: хэш не совпадает → обновляем хэш, меняем на updated"""
        print("\n🧪 Тест: Изменённый файл со статусом 'added'")
        
        # Создаём файл
        file_meta = self._create_file('changed_added.txt', 'new_content')
        
        # Вставляем с ДРУГИМ хэшем и статусом added
        self._insert_record(file_meta['path'], 'old_hash_123', 'added', file_meta['size'])
        
        # Синхронизируем
        stats = self.db.sync_by_hash([file_meta])
        
        # Проверяем: статус должен стать updated, хэш обновиться
        assert self._get_status(file_meta['path']) == 'updated', "Статус должен стать 'updated'"
        assert self._get_hash(file_meta['path']) == file_meta['hash'], "Хэш должен обновиться"
        assert stats['updated'] == 1, "Должен быть 1 обновлённый файл"
        print("✅ Passed: added + hash_differs → updated с новым хэшем")
    
    def test_row3_hash_differs_all_statuses(self):
        """Строка 3: тест всех статусов при изменении хэша"""
        print("\n🧪 Тест: Изменённый файл - все статусы")
        
        statuses = ['added', 'updated', 'processed', 'deleted', 'ok', 'error', None]
        disk_files = []
        
        for status in statuses:
            status_str = 'NULL' if status is None else status
            filename = f'changed_{status_str}.txt'
            
            # Создаём файл с новым содержимым
            file_meta = self._create_file(filename, f'new_content_{status_str}')
            disk_files.append(file_meta)
            
            # Вставляем с ДРУГИМ хэшем
            self._insert_record(file_meta['path'], 'old_hash_' + status_str, status, file_meta['size'])
        
        # Синхронизируем
        stats = self.db.sync_by_hash(disk_files)
        
        # Проверяем: ВСЕ должны стать updated с новым хэшем
        for status in statuses:
            status_str = 'NULL' if status is None else status
            filename = f'changed_{status_str}.txt'
            
            current_status = self._get_status(filename)
            current_hash = self._get_hash(filename)
            
            assert current_status == 'updated', \
                f"{filename}: статус должен быть 'updated', получили '{current_status}'"
            
            # Находим актуальный хэш с диска
            actual_hash = next(f['hash'] for f in disk_files if f['path'] == filename)
            assert current_hash == actual_hash, \
                f"{filename}: хэш должен обновиться"
        
        assert stats['updated'] == 7, "Должно быть 7 обновлённых файлов"
        print("✅ Passed: Хэш изменился - все статусы → updated с новым хэшем")
    
    # ========== ДОПОЛНИТЕЛЬНЫЕ ТЕСТЫ ==========
    
    def test_new_file_added(self):
        """Тест: новый файл (путь отсутствует в БД) → added"""
        print("\n🧪 Тест: Новый файл")
        
        # Создаём файл (без записи в БД)
        file_meta = self._create_file('new_file.txt', 'brand_new')
        
        # Синхронизируем
        stats = self.db.sync_by_hash([file_meta])
        
        # Проверяем: должен добавиться со статусом added
        assert self._get_status(file_meta['path']) == 'added', "Статус должен быть 'added'"
        assert stats['added'] == 1, "Должен быть 1 добавленный файл"
        print("✅ Passed: Новый файл → added")
    
    def run_all_tests(self):
        """Запуск всех тестов"""
        print("\n" + "="*60)
        print("ЗАПУСК ТЕСТОВ СИНХРОНИЗАЦИИ")
        print("="*60)
        
        tests = [
            # Строка 1: Удаление
            self.test_row1_deleted_file_status_added,
            self.test_row1_deleted_file_all_statuses,
            
            # Строка 2: Хэш совпадает
            self.test_row2_hash_matches_added,
            self.test_row2_hash_matches_all_statuses,
            
            # Строка 3: Хэш не совпадает
            self.test_row3_hash_differs_added,
            self.test_row3_hash_differs_all_statuses,
            
            # Дополнительные
            self.test_new_file_added,
        ]
        
        passed = 0
        failed = 0
        
        for test_func in tests:
            try:
                # Очищаем БД и директорию перед каждым тестом
                with self.db.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(f"TRUNCATE TABLE {self.db.table_name}")
                
                for file in Path(self.test_dir).glob('*'):
                    file.unlink()
                
                # Запускаем тест
                test_func()
                passed += 1
                
            except AssertionError as e:
                print(f"❌ FAILED: {e}")
                failed += 1
            except Exception as e:
                print(f"💥 ERROR: {e}")
                failed += 1
        
        print("\n" + "="*60)
        print(f"РЕЗУЛЬТАТЫ: {passed} passed, {failed} failed")
        print("="*60)
        
        return failed == 0


def main():
    """Точка входа для запуска тестов"""
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        print("❌ ERROR: DATABASE_URL not set")
        sys.exit(1)
    
    test_suite = TestSyncLogic(database_url)
    
    try:
        success = test_suite.run_all_tests()
        sys.exit(0 if success else 1)
    finally:
        test_suite.cleanup()


if __name__ == '__main__':
    main()
