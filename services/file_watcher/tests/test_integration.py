"""Интеграционные тесты file-watcher

Проверяет полные сценарии работы с файлами:
- Добавление → status=added
- Изменение → status=updated
- Удаление → status=deleted
- Различные комбинации переходов между статусами
- Фильтрация по расширениям
"""

import os
import sys
import time
import tempfile
import shutil
from pathlib import Path

# Добавляем src/ и корень репозитория в PYTHONPATH
src_path = Path(__file__).parent.parent / "src"
repo_root = Path(__file__).resolve().parents[3]
for extra_path in (src_path, repo_root):
    if str(extra_path) not in sys.path:
        sys.path.insert(0, str(extra_path))

from utils.database import PostgreDataBase
from scanner import Scanner
from vector_sync import VectorSync


class TestFileWatcher:
    """Интеграционные тесты file-watcher"""
    
    def setup_method(self):
        """Подготовка перед каждым тестом"""
        # Создаём временную папку для тестов
        self.test_folder = tempfile.mkdtemp()
        
        # Загружаем DATABASE_URL из settings
        from settings import settings
        self.db = PostgreDataBase(database_url=settings.DATABASE_URL)
        
        # Очищаем таблицу files перед тестом
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM files WHERE path LIKE 'test_%'")
        
        # Инициализируем компоненты
        from file_filter import FileFilter
        # Для тестов создаём фильтр без ограничений
        test_filter = FileFilter(min_size=0, max_size=100*1024*1024, excluded_dirs=[], excluded_patterns=[])
        self.scanner = Scanner(self.test_folder, ['.txt', '.pdf', '.docx'], test_filter)
        self.vector_sync = VectorSync(self.db)
    
    def run_all_tests(self) -> bool:
        """Запускает все тесты класса. Возвращает True если все прошли."""
        import traceback
        
        test_methods = [
            method for method in dir(self)
            if method.startswith('test_') and callable(getattr(self, method))
        ]
        
        passed = 0
        failed = 0
        
        for test_name in sorted(test_methods):
            try:
                self.setup_method()  # Инициализация перед каждым тестом
                getattr(self, test_name)()
                passed += 1
            except Exception as e:
                failed += 1
                print(f"  ✗ {test_name}: {e}")
                # traceback.print_exc()  # Отключаем полный traceback для краткости
            finally:
                # Очистка после каждого теста
                try:
                    self.teardown_method()
                except:
                    pass
        
        print(f"  📊 Результаты: {passed} passed, {failed} failed")
        
        # Финальная очистка БД
        try:
            # Нужен setup для инициализации self.db
            if not hasattr(self, 'db'):
                self.setup_method()
            self._cleanup_test_records()
        except Exception as e:
            print(f"  ⚠ Ошибка очистки БД: {e}")
        
        return failed == 0
    
    def teardown_method(self):
        """Очистка после каждого теста"""
        # Удаляем тестовые файлы
        import shutil
        if os.path.exists(self.test_folder):
            shutil.rmtree(self.test_folder)
        
        # Очищаем БД от тестовых записей
        self._cleanup_test_records()
    
    def _cleanup_test_records(self):
        """Удаляет все тестовые записи из БД"""
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                # Удаляем записи с тестовыми именами файлов
                cur.execute("""
                    DELETE FROM files 
                    WHERE path LIKE 'test_%' 
                       OR path LIKE '%test%.txt'
                       OR path LIKE '%test%.pdf'
                       OR path LIKE '%test%.docx'
                       OR path LIKE 'file%.txt'
                       OR path LIKE 'file%.pdf'
                       OR path LIKE 'allowed%'
                       OR path LIKE 'ignored%'
                       OR path LIKE 'rapid_%'
                """)
    
    def run_cycle(self):
        """Запускает один цикл сканирования (эмулирует main.py)"""
        files = self.scanner.scan()
        sync_stats = self.db.sync_by_hash(files)
        status_stats = self.vector_sync.sync_status()
        return sync_stats, status_stats
    
    def get_file_status(self, filename: str) -> str:
        """Получает status_sync файла из БД"""
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT status_sync FROM files WHERE path = %s",
                    (filename,)
                )
                row = cur.fetchone()
                return row[0] if row else None
    
    def test_01_add_file(self):
        """Тест 1: Добавление файла → status=added"""
        # Создаём файл
        test_file = Path(self.test_folder) / "test_file.txt"
        test_file.write_text("Initial content")
        
        # Запускаем цикл
        sync_stats, status_stats = self.run_cycle()
        
        # Проверяем результаты
        assert sync_stats['added'] == 1, "Должен быть добавлен 1 файл"
        assert self.get_file_status("test_file.txt") == "added", "Статус должен быть 'added'"
        
        print("✓ Тест 1 пройден: файл добавлен, status=added")
    
    def test_02_update_file(self):
        """Тест 2: Изменение файла → status=updated"""
        test_file = Path(self.test_folder) / "test_file.txt"
        
        # Шаг 1: Добавляем файл
        test_file.write_text("Initial content")
        self.run_cycle()
        assert self.get_file_status("test_file.txt") == "added"
        
        # Небольшая пауза чтобы mtime точно изменился
        time.sleep(0.1)
        
        # Шаг 2: Изменяем файл
        test_file.write_text("Updated content")
        sync_stats, status_stats = self.run_cycle()
        
        # Проверяем результаты
        assert sync_stats['updated'] == 1, "Должен быть обновлён 1 файл"
        assert self.get_file_status("test_file.txt") == "updated", "Статус должен быть 'updated'"
        
        print("✓ Тест 2 пройден: файл изменён, status=updated")
    
    def test_03_delete_file(self):
        """Тест 3: Удаление файла → status=deleted"""
        test_file = Path(self.test_folder) / "test_file.txt"
        
        # Шаг 1: Добавляем файл
        test_file.write_text("Initial content")
        self.run_cycle()
        assert self.get_file_status("test_file.txt") == "added"
        
        # Шаг 2: Удаляем файл
        test_file.unlink()
        sync_stats, status_stats = self.run_cycle()
        
        # Проверяем результаты
        assert sync_stats['deleted'] == 1, "Должен быть помечен 1 удалённый файл"
        assert self.get_file_status("test_file.txt") == "deleted", "Статус должен быть 'deleted'"
        
        print("✓ Тест 3 пройден: файл удалён, status=deleted")
    
    def test_04_complex_lifecycle(self):
        """Тест 4: Сложный жизненный цикл файла
        
        Сценарий:
        1. Добавление → added
        2. Изменение → updated
        3. Изменение → updated (остаётся)
        4. Удаление → deleted
        5. Повторное добавление → added
        """
        test_file = Path(self.test_folder) / "test_lifecycle.txt"
        
        # Шаг 1: Добавление
        test_file.write_text("Version 1")
        self.run_cycle()
        assert self.get_file_status("test_lifecycle.txt") == "added", "Шаг 1: должен быть added"
        print("  Шаг 1/5: added ✓")
        
        time.sleep(0.1)
        
        # Шаг 2: Первое изменение
        test_file.write_text("Version 2")
        self.run_cycle()
        assert self.get_file_status("test_lifecycle.txt") == "updated", "Шаг 2: должен быть updated"
        print("  Шаг 2/5: updated ✓")
        
        time.sleep(0.1)
        
        # Шаг 3: Второе изменение
        test_file.write_text("Version 3")
        sync_stats, _ = self.run_cycle()
        assert sync_stats['updated'] == 1, "Шаг 3: должно быть обнаружено обновление"
        assert self.get_file_status("test_lifecycle.txt") == "updated", "Шаг 3: статус остаётся updated"
        print("  Шаг 3/5: updated (повторно) ✓")
        
        # Шаг 4: Удаление
        test_file.unlink()
        self.run_cycle()
        assert self.get_file_status("test_lifecycle.txt") == "deleted", "Шаг 4: должен быть deleted"
        print("  Шаг 4/5: deleted ✓")
        
        # Шаг 5: Повторное добавление (как новый файл)
        test_file.write_text("Version 4 (new)")
        sync_stats, _ = self.run_cycle()
        # При повторном добавлении файл уже есть в БД, но с новым хешем
        assert sync_stats['updated'] == 1, "Шаг 5: должно быть обновление записи"
        assert self.get_file_status("test_lifecycle.txt") == "updated", "Шаг 5: должен быть updated"
        print("  Шаг 5/5: updated (после удаления) ✓")
        
        print("✓ Тест 4 пройден: сложный жизненный цикл")
    
    def test_05_multiple_files(self):
        """Тест 5: Работа с несколькими файлами одновременно"""
        files = {
            'file1.txt': 'Content 1',
            'file2.txt': 'Content 2',
            'file3.txt': 'Content 3'
        }
        
        # Создаём все файлы
        for name, content in files.items():
            (Path(self.test_folder) / name).write_text(content)
        
        sync_stats, _ = self.run_cycle()
        assert sync_stats['added'] == 3, "Должно быть добавлено 3 файла"
        
        # Проверяем статусы
        for name in files.keys():
            assert self.get_file_status(name) == "added"
        
        time.sleep(0.1)
        
        # Изменяем один файл
        (Path(self.test_folder) / 'file2.txt').write_text("Updated content")
        sync_stats, _ = self.run_cycle()
        assert sync_stats['updated'] == 1, "Должен быть обновлён 1 файл"
        assert self.get_file_status('file2.txt') == "updated"
        
        # Удаляем один файл
        (Path(self.test_folder) / 'file3.txt').unlink()
        sync_stats, _ = self.run_cycle()
        assert sync_stats['deleted'] == 1, "Должен быть удалён 1 файл"
        assert self.get_file_status('file3.txt') == "deleted"
        
        # Остальные не изменились
        assert self.get_file_status('file1.txt') == "added"
        
        print("✓ Тест 5 пройден: работа с несколькими файлами")
    
    def test_06_extension_filter(self):
        """Тест 6: Фильтрация по расширениям"""
        test_files = {
            'allowed1.txt': True,   # Должен быть обработан
            'allowed2.pdf': True,   # Должен быть обработан
            'allowed3.docx': True,  # Должен быть обработан
            'ignored1.csv': False,  # Должен быть проигнорирован
            'ignored2.jpg': False,  # Должен быть проигнорирован
            'ignored3.py': False,   # Должен быть проигнорирован
        }
        
        # Создаём все файлы
        for name in test_files.keys():
            (Path(self.test_folder) / name).write_text(f"Content of {name}")
        
        sync_stats, _ = self.run_cycle()
        
        # Должно быть обработано только 3 файла с разрешёнными расширениями
        assert sync_stats['added'] == 3, f"Должно быть добавлено 3 файла, получено: {sync_stats['added']}"
        
        # Проверяем что обработаны только разрешённые файлы
        for name, should_exist in test_files.items():
            status = self.get_file_status(name)
            if should_exist:
                assert status == "added", f"Файл {name} должен быть в БД со статусом 'added'"
            else:
                assert status is None, f"Файл {name} НЕ должен быть в БД"
        
        print("✓ Тест 6 пройден: фильтрация по расширениям работает")
    
    def test_07_extension_filter_after_change(self):
        """Тест 7: Переименование файла с изменением расширения"""
        # Создаём файл с разрешённым расширением
        file1 = Path(self.test_folder) / "test_file.txt"
        file1.write_text("Content")
        self.run_cycle()
        assert self.get_file_status("test_file.txt") == "added"
        
        # "Переименовываем" (удаляем старый, создаём новый с другим расширением)
        file1.unlink()
        file2 = Path(self.test_folder) / "test_file.csv"  # Неразрешённое расширение
        file2.write_text("Content")
        
        sync_stats, _ = self.run_cycle()
        
        # Старый файл должен быть помечен как удалённый
        assert self.get_file_status("test_file.txt") == "deleted"
        
        # Новый файл с .csv не должен попасть в БД
        assert self.get_file_status("test_file.csv") is None
        
        print("✓ Тест 7 пройден: переименование с изменением расширения")
    
    def test_08_rapid_changes(self):
        """Тест 8: Быстрые изменения файла"""
        test_file = Path(self.test_folder) / "rapid_test.txt"
        
        # Создаём файл
        test_file.write_text("Version 1")
        self.run_cycle()
        
        # Быстро изменяем несколько раз
        for i in range(2, 6):
            time.sleep(0.1)
            test_file.write_text(f"Version {i}")
            sync_stats, _ = self.run_cycle()
            status = self.get_file_status("rapid_test.txt")
            assert status == "updated", f"После изменения {i} статус должен быть 'updated'"
        
        print("✓ Тест 8 пройден: быстрые изменения обрабатываются корректно")
    
    def test_09_delete_and_restore_same_content(self):
        """Тест 9: Удаление и восстановление файла с тем же контентом
        
        Этот тест проверяет edge case: файл удаляется, а затем восстанавливается
        с ТОЧНО ТЕМ ЖЕ содержимым (тот же хеш). Статус всё равно должен измениться.
        """
        test_file = Path(self.test_folder) / "restore_test.txt"
        content = "Fixed content that won't change"
        
        # Шаг 1: Создаём файл
        test_file.write_text(content)
        self.run_cycle()
        assert self.get_file_status("restore_test.txt") == "added"
        print("  Шаг 1/3: файл создан, status=added ✓")
        
        # Шаг 2: Удаляем файл
        test_file.unlink()
        self.run_cycle()
        assert self.get_file_status("restore_test.txt") == "deleted"
        print("  Шаг 2/3: файл удалён, status=deleted ✓")
        
        # Шаг 3: Восстанавливаем с ТЕМ ЖЕ контентом
        test_file.write_text(content)  # Тот же контент!
        sync_stats, _ = self.run_cycle()
        
        # КРИТИЧНО: статус должен измениться с deleted на updated
        # даже если хеш не изменился
        status = self.get_file_status("restore_test.txt")
        assert status == "updated", f"Файл должен быть updated, но статус: {status}"
        assert sync_stats['updated'] >= 1, "Должно быть обнаружено обновление"
        print("  Шаг 3/3: файл восстановлен с тем же контентом, status=updated ✓")
        
        print("✓ Тест 9 пройден: восстановление с тем же контентом работает")


def run_tests():
    """Запускает все тесты"""
    import traceback
    
    test_class = TestFileWatcher()
    test_methods = [
        method for method in dir(test_class)
        if method.startswith('test_') and callable(getattr(test_class, method))
    ]
    
    print("=" * 60)
    print("ЗАПУСК ИНТЕГРАЦИОННЫХ ТЕСТОВ FILE-WATCHER")
    print("=" * 60)
    print()
    
    passed = 0
    failed = 0
    
    for test_name in sorted(test_methods):
        try:
            print(f"Запуск {test_name}...")
            test_class.setup_method()
            getattr(test_class, test_name)()
            test_class.teardown_method()
            passed += 1
            print()
        except AssertionError as e:
            failed += 1
            print(f"✗ ОШИБКА в {test_name}: {e}")
            traceback.print_exc()
            print()
        except Exception as e:
            failed += 1
            print(f"✗ ИСКЛЮЧЕНИЕ в {test_name}: {e}")
            traceback.print_exc()
            print()
    
    print("=" * 60)
    print(f"РЕЗУЛЬТАТЫ: {passed} пройдено, {failed} провалено")
    print("=" * 60)
    
    # Финальная очистка БД от всех тестовых записей
    if passed + failed > 0:
        print("\nОчистка БД от тестовых записей...")
        try:
            test_class._cleanup_test_records()
            print("✓ БД очищена")
        except Exception as e:
            print(f"⚠ Ошибка при очистке БД: {e}")
    
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
