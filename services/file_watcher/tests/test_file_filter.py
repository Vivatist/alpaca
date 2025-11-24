"""Тесты для модуля фильтрации файлов"""

import os
import sys
import tempfile
from pathlib import Path

# Добавляем src/ в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from file_filter import FileFilter


class TestFileFilter:
    """Тесты фильтрации файлов"""
    
    def setup_method(self):
        """Подготовка перед каждым тестом"""
        self.test_folder = tempfile.mkdtemp()
    
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
                self.setup_method()
                getattr(self, test_name)()
                self.teardown_method()
                passed += 1
            except Exception as e:
                failed += 1
                print(f"  ✗ {test_name}: {e}")
                traceback.print_exc()
        
        print(f"  📊 Результаты: {passed} passed, {failed} failed")
        return failed == 0
    
    def teardown_method(self):
        """Очистка после каждого теста"""
        import shutil
        if os.path.exists(self.test_folder):
            shutil.rmtree(self.test_folder)
    
    def test_01_size_filter_minimum(self):
        """Тест 1: Фильтрация по минимальному размеру"""
        file_filter = FileFilter(min_size=500, max_size=10*1024*1024)
        
        # Маленький файл (должен быть отфильтрован)
        small_file = Path(self.test_folder) / "small.txt"
        small_file.write_text("x" * 100)  # 100 байт
        assert file_filter.should_skip_file(small_file), "Файл < 500 байт должен быть пропущен"
        
        # Файл ровно 500 байт (не должен быть отфильтрован)
        exact_file = Path(self.test_folder) / "exact.txt"
        exact_file.write_text("x" * 500)
        assert not file_filter.should_skip_file(exact_file), "Файл = 500 байт не должен быть пропущен"
        
        # Большой файл (не должен быть отфильтрован)
        large_file = Path(self.test_folder) / "large.txt"
        large_file.write_text("x" * 1000)
        assert not file_filter.should_skip_file(large_file), "Файл > 500 байт не должен быть пропущен"
        
        print("✓ Тест 1 пройден: фильтрация по минимальному размеру")
    
    def test_02_size_filter_maximum(self):
        """Тест 2: Фильтрация по максимальному размеру"""
        file_filter = FileFilter(min_size=500, max_size=10*1024*1024)  # 10 МБ
        
        # Файл меньше лимита
        ok_file = Path(self.test_folder) / "ok.txt"
        ok_file.write_text("x" * 1000)
        assert not file_filter.should_skip_file(ok_file), "Файл < 10 МБ не должен быть пропущен"
        
        # Файл больше лимита
        huge_file = Path(self.test_folder) / "huge.txt"
        huge_file.write_text("x" * (11*1024*1024))  # 11 МБ
        assert file_filter.should_skip_file(huge_file), "Файл > 10 МБ должен быть пропущен"
        
        print("✓ Тест 2 пройден: фильтрация по максимальному размеру")
    
    def test_03_directory_filter(self):
        """Тест 3: Фильтрация директорий"""
        file_filter = FileFilter(
            min_size=0,
            max_size=100*1024*1024,
            excluded_dirs=['TMP', 'temp', 'cache']
        )
        
        # Исключенные директории
        assert file_filter.should_skip_directory('TMP'), "TMP должна быть пропущена"
        assert file_filter.should_skip_directory('temp'), "temp должна быть пропущена"
        assert file_filter.should_skip_directory('cache'), "cache должна быть пропущена"
        
        # Скрытые директории (всегда пропускаются)
        assert file_filter.should_skip_directory('.git'), ".git должна быть пропущена"
        assert file_filter.should_skip_directory('.hidden'), ".hidden должна быть пропущена"
        
        # Разрешенные директории
        assert not file_filter.should_skip_directory('data'), "data не должна быть пропущена"
        assert not file_filter.should_skip_directory('documents'), "documents не должна быть пропущена"
        
        print("✓ Тест 3 пройден: фильтрация директорий")
    
    def test_04_pattern_filter(self):
        """Тест 4: Фильтрация по шаблонам имен"""
        file_filter = FileFilter(
            min_size=0,
            max_size=100*1024*1024,
            excluded_dirs=[],
            excluded_patterns=['~*', '.*', '*.tmp']
        )
        
        # Создаем файлы для тестирования
        test_cases = {
            '~temp.txt': True,      # Должен быть пропущен (начинается с ~)
            '.hidden.txt': True,    # Должен быть пропущен (начинается с .)
            'file.tmp': True,       # Должен быть пропущен (расширение .tmp)
            'normal.txt': False,    # Не должен быть пропущен
            'document.pdf': False,  # Не должен быть пропущен
        }
        
        for filename, should_skip in test_cases.items():
            test_file = Path(self.test_folder) / filename
            test_file.write_text("test content" * 100)  # Достаточный размер
            
            result = file_filter.should_skip_file(test_file)
            assert result == should_skip, f"Файл {filename}: ожидалось skip={should_skip}, получено {result}"
        
        print("✓ Тест 4 пройден: фильтрация по шаблонам")
    
    def test_05_from_env(self):
        """Тест 5: Создание фильтра из переменных окружения"""
        # Устанавливаем переменные окружения
        os.environ['FILE_MIN_SIZE'] = '1000'
        os.environ['FILE_MAX_SIZE'] = '5000000'  # 5 МБ
        os.environ['EXCLUDED_DIRS'] = 'TMP, cache, temp'
        os.environ['EXCLUDED_PATTERNS'] = '~*, .*, *.bak'
        
        file_filter = FileFilter.from_env()
        
        # Проверяем что параметры правильно считаны
        assert file_filter.min_size == 1000
        assert file_filter.max_size == 5000000
        assert 'TMP' in file_filter.excluded_dirs
        assert 'cache' in file_filter.excluded_dirs
        assert 'temp' in file_filter.excluded_dirs
        assert '~*' in file_filter.excluded_patterns
        assert '.*' in file_filter.excluded_patterns
        assert '*.bak' in file_filter.excluded_patterns
        
        # Проверяем работу
        small_file = Path(self.test_folder) / "small.txt"
        small_file.write_text("x" * 500)
        assert file_filter.should_skip_file(small_file), "Маленький файл должен быть пропущен"
        
        backup_file = Path(self.test_folder) / "file.bak"
        backup_file.write_text("x" * 2000)
        assert file_filter.should_skip_file(backup_file), "Файл .bak должен быть пропущен"
        
        print("✓ Тест 5 пройден: создание из переменных окружения")
    
    def test_06_combined_filters(self):
        """Тест 6: Комбинированные фильтры"""
        file_filter = FileFilter(
            min_size=500,
            max_size=10*1024*1024,
            excluded_dirs=['TMP'],
            excluded_patterns=['~*', '.*']
        )
        
        # Файл проходит по размеру, но не проходит по шаблону
        temp_file = Path(self.test_folder) / "~temp.txt"
        temp_file.write_text("x" * 1000)
        assert file_filter.should_skip_file(temp_file), "Файл должен быть пропущен по шаблону"
        
        # Файл проходит по шаблону, но не проходит по размеру
        small_file = Path(self.test_folder) / "small.txt"
        small_file.write_text("x" * 100)
        assert file_filter.should_skip_file(small_file), "Файл должен быть пропущен по размеру"
        
        # Файл проходит все фильтры
        good_file = Path(self.test_folder) / "good.txt"
        good_file.write_text("x" * 1000)
        assert not file_filter.should_skip_file(good_file), "Файл не должен быть пропущен"
        
        print("✓ Тест 6 пройден: комбинированные фильтры")
    
    def test_07_edge_cases(self):
        """Тест 7: Граничные случаи"""
        file_filter = FileFilter(min_size=500, max_size=10*1024*1024)
        
        # Пустой файл
        empty_file = Path(self.test_folder) / "empty.txt"
        empty_file.write_text("")
        assert file_filter.should_skip_file(empty_file), "Пустой файл должен быть пропущен"
        
        # Файл ровно на границе минимума
        min_file = Path(self.test_folder) / "min.txt"
        min_file.write_text("x" * 500)
        assert not file_filter.should_skip_file(min_file), "Файл на минимальной границе не должен быть пропущен"
        
        # Файл ровно на границе максимума
        max_file = Path(self.test_folder) / "max.txt"
        max_file.write_text("x" * (10*1024*1024))
        assert not file_filter.should_skip_file(max_file), "Файл на максимальной границе не должен быть пропущен"
        
        # Файл чуть больше максимума
        over_file = Path(self.test_folder) / "over.txt"
        over_file.write_text("x" * (10*1024*1024 + 1))
        assert file_filter.should_skip_file(over_file), "Файл больше максимума должен быть пропущен"
        
        print("✓ Тест 7 пройден: граничные случаи")


def run_tests():
    """Запускает все тесты"""
    import traceback
    
    test_class = TestFileFilter()
    test_methods = [
        method for method in dir(test_class)
        if method.startswith('test_') and callable(getattr(test_class, method))
    ]
    
    print("=" * 60)
    print("ЗАПУСК ТЕСТОВ ФИЛЬТРАЦИИ ФАЙЛОВ")
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
    
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
