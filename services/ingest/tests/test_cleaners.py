"""
Тесты для клинеров.
"""
import pytest
from cleaners import simple_cleaner, stamps_cleaner, build_cleaner, CLEANERS


class TestSimpleCleaner:
    """Тесты simple_cleaner."""
    
    def test_removes_extra_whitespace(self):
        """Удаляет лишние пробелы."""
        text = "Текст   с    лишними   пробелами"
        result = simple_cleaner(text)
        
        assert "   " not in result
        assert "Текст" in result
    
    def test_normalizes_newlines(self):
        """Нормализует переносы строк."""
        text = "Строка1\n\n\n\nСтрока2"
        result = simple_cleaner(text)
        
        assert "\n\n\n\n" not in result
    
    def test_preserves_content(self):
        """Сохраняет основной контент."""
        text = "Важный текст документа"
        result = simple_cleaner(text)
        
        assert "Важный" in result
        assert "документа" in result
    
    def test_empty_text(self):
        """Пустой текст возвращает пустую строку."""
        assert simple_cleaner("") == ""
        assert simple_cleaner("   ") == ""


class TestStampsCleaner:
    """Тесты stamps_cleaner."""
    
    def test_removes_stamp_pattern(self):
        """Удаляет штампы 'Прошито, пронумеровано на ___ листах'."""
        text = "Документ\n\nПрошито, пронумеровано на ___ листах. Иванов И.И. ___\n\nКонец"
        result = stamps_cleaner(text)
        
        assert "Прошито" not in result
        assert "пронумеровано" not in result
        assert "Документ" in result
        assert "Конец" in result
    
    def test_preserves_normal_text(self):
        """Не трогает обычный текст."""
        text = "Обычный текст без штампов"
        result = stamps_cleaner(text)
        
        assert result == text
    
    def test_normalizes_underscores(self):
        """Нормализует множественные underscores."""
        text = "Подпись _________ дата"
        result = stamps_cleaner(text)
        
        assert "___" in result
        assert "________" not in result


class TestCleanerRegistry:
    """Тесты реестра клинеров."""
    
    def test_registry_has_cleaners(self):
        """Реестр содержит клинеры."""
        assert "simple" in CLEANERS
        assert "stamps" in CLEANERS
    
    def test_build_cleaner_returns_callable(self):
        """build_cleaner возвращает callable."""
        cleaner = build_cleaner()
        assert callable(cleaner)
    
    def test_pipeline_applies_all_cleaners(self):
        """Пайплайн применяет все клинеры."""
        cleaner = build_cleaner()
        text = "Текст   с   пробелами\n\nПрошито, пронумеровано на ___ листах. ФИО ___"
        result = cleaner(text)
        
        # simple_cleaner убрал лишние пробелы
        assert "   " not in result
