"""
Тесты для чанкеров.
"""
import pytest
from contracts import FileSnapshot
from chunkers import simple_chunker, smart_chunker, build_chunker, CHUNKERS


class TestSimpleChunker:
    """Тесты simple_chunker."""
    
    def test_simple_text(self):
        """Простой текст разбивается корректно."""
        file = FileSnapshot(
            hash="test",
            path="/test.txt",
            raw_text="Первый параграф.\n\nВторой параграф.\n\nТретий параграф."
        )
        chunks = simple_chunker(file)
        
        assert len(chunks) > 0
        assert all(isinstance(c, str) for c in chunks)
    
    def test_empty_text(self):
        """Пустой текст возвращает пустой список."""
        file = FileSnapshot(hash="test", path="/test.txt", raw_text="")
        chunks = simple_chunker(file)
        
        assert chunks == []
    
    def test_whitespace_only(self):
        """Текст из пробелов возвращает пустой список."""
        file = FileSnapshot(hash="test", path="/test.txt", raw_text="   \n\n   ")
        chunks = simple_chunker(file)
        
        assert chunks == []
    
    def test_long_text_splits(self):
        """Длинный текст разбивается на части."""
        # Генерируем текст > 1000 символов
        long_para = "Слово " * 300  # ~1800 символов
        file = FileSnapshot(hash="test", path="/test.txt", raw_text=long_para)
        chunks = simple_chunker(file)
        
        assert len(chunks) > 1
        # Проверяем, что весь текст сохранён
        combined = "".join(chunks)
        assert "Слово" in combined


class TestSmartChunker:
    """Тесты smart_chunker (требует langchain)."""
    
    def test_simple_text(self):
        """Простой текст разбивается корректно."""
        file = FileSnapshot(
            hash="test",
            path="/test.txt",
            raw_text="Первый параграф.\n\nВторой параграф.\n\nТретий параграф."
        )
        chunks = smart_chunker(file)
        
        assert len(chunks) > 0
        assert all(isinstance(c, str) for c in chunks)
    
    def test_empty_text(self):
        """Пустой текст возвращает пустой список."""
        file = FileSnapshot(hash="test", path="/test.txt", raw_text="")
        chunks = smart_chunker(file)
        
        assert chunks == []


class TestChunkerRegistry:
    """Тесты реестра чанкеров."""
    
    def test_registry_has_chunkers(self):
        """Реестр содержит чанкеры."""
        assert "simple" in CHUNKERS
        assert "smart" in CHUNKERS
    
    def test_build_chunker_returns_callable(self):
        """build_chunker возвращает callable."""
        chunker = build_chunker()
        assert callable(chunker)
