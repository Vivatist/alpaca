"""
Тесты для контрактов (моделей данных).
"""
import pytest
from contracts import FileSnapshot


class TestFileSnapshot:
    """Тесты FileSnapshot."""
    
    def test_create_minimal(self):
        """Создание с минимальными полями."""
        file = FileSnapshot(hash="abc123", path="docs/test.txt")
        
        assert file.hash == "abc123"
        assert file.path == "docs/test.txt"
        assert file.raw_text == ""
    
    def test_create_with_raw_text(self):
        """Создание с raw_text."""
        file = FileSnapshot(
            hash="abc123",
            path="docs/test.txt",
            raw_text="Содержимое файла"
        )
        
        assert file.raw_text == "Содержимое файла"
    
    def test_full_path_property(self):
        """Свойство full_path вычисляется из MONITORED_PATH + path."""
        file = FileSnapshot(hash="abc123", path="docs/test.txt")
        
        # full_path = MONITORED_PATH + "/" + path
        assert file.full_path.endswith("docs/test.txt")
        assert "monitored" in file.full_path.lower() or "/tmp/" in file.full_path
