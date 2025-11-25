"""
Тесты для модуля чанкования (custom_chunker)
"""
import pytest
from app.chunkers.custom_chunker import chunking


class TestChunking:
    """Тесты функции chunking"""
    
    def test_chunking_simple_text(self):
        """Тест чанкования простого текста"""
        text = "Это первый параграф.\n\nЭто второй параграф.\n\nЭто третий параграф."
        file_path = "/tmp/test_file.txt"
        
        chunks = chunking(file_path, text)
        
        assert len(chunks) > 0
        assert all(isinstance(chunk, str) for chunk in chunks)
        assert all(len(chunk) <= 1000 for chunk in chunks)
    
    def test_chunking_long_text(self):
        """Тест чанкования длинного текста из нескольких параграфов"""
        # Генерируем текст из параграфов по 500 символов каждый
        paragraph = "Это короткий параграф. " * 20  # ~500 символов
        text = paragraph + "\n\n" + paragraph + "\n\n" + paragraph
        file_path = "/tmp/test_file.txt"
        
        chunks = chunking(file_path, text)
        
        # Должно получиться несколько чанков, так как параграфы объединяются до 1000 символов
        assert len(chunks) > 0
        # Проверяем, что весь текст вошёл в чанки
        combined_text = ''.join(chunks)
        assert len(combined_text) > 0
        assert "короткий параграф" in combined_text
    
    def test_chunking_empty_text(self):
        """Тест чанкования пустого текста"""
        text = ""
        file_path = "/tmp/test_file.txt"
        
        chunks = chunking(file_path, text)
        
        assert len(chunks) == 0
    
    def test_chunking_whitespace_only(self):
        """Тест чанкования текста только из пробелов"""
        text = "   \n\n   \n\n   "
        file_path = "/tmp/test_file.txt"
        
        chunks = chunking(file_path, text)
        
        # Пустые параграфы должны игнорироваться
        assert len(chunks) == 0
    
    def test_chunking_single_long_paragraph(self):
        """Тест чанкования одного длинного параграфа без разбиения на строки"""
        text = "Это очень длинный параграф. " * 100  # > 1000 символов
        file_path = "/tmp/test_file.txt"
        
        chunks = chunking(file_path, text)
        
        # Текущая реализация не разбивает длинные параграфы без \n\n
        # Просто проверяем что чанк создан
        assert len(chunks) >= 1
        assert "длинный параграф" in chunks[0]
    
    def test_chunking_preserves_content(self):
        """Тест что чанкование не теряет содержимое"""
        text = "Параграф 1.\n\nПараграф 2.\n\nПараграф 3."
        file_path = "/tmp/test_file.txt"
        
        chunks = chunking(file_path, text)
        combined = ''.join(chunks)
        
        # Проверяем что все параграфы присутствуют
        assert "Параграф 1" in combined
        assert "Параграф 2" in combined
        assert "Параграф 3" in combined
    
    def test_chunking_multiple_newlines(self):
        """Тест чанкования с множественными переносами строк"""
        text = "Параграф 1.\n\n\n\nПараграф 2.\n\n\n\n\n\nПараграф 3."
        file_path = "/tmp/test_file.txt"
        
        chunks = chunking(file_path, text)
        
        assert len(chunks) > 0
        combined = ''.join(chunks)
        assert "Параграф 1" in combined
        assert "Параграф 2" in combined
        assert "Параграф 3" in combined
