"""
Тесты для парсеров.
"""
import pytest
from contracts import FileSnapshot
from parsers import ParserRegistry, build_parser_registry, TXTParser


class TestTXTParser:
    """Тесты TXTParser."""
    
    def test_parse_utf8_file(self, tmp_path):
        """Парсит UTF-8 файл."""
        # Создаём временный файл
        test_file = tmp_path / "test.txt"
        test_file.write_text("Тестовый текст на русском языке", encoding='utf-8')
        
        parser = TXTParser()
        file = FileSnapshot(hash="test", path=str(test_file))
        # Подменяем full_path напрямую через __dict__ для теста
        file.__dict__['_full_path'] = str(test_file)
        
        # Мокаем full_path property
        import unittest.mock as mock
        with mock.patch.object(FileSnapshot, 'full_path', new_callable=mock.PropertyMock) as mock_fp:
            mock_fp.return_value = str(test_file)
            result = parser.parse(file)
        
        assert "Тестовый текст" in result
        assert "русском" in result
    
    def test_parse_nonexistent_file_raises(self):
        """Несуществующий файл вызывает исключение."""
        import unittest.mock as mock
        
        parser = TXTParser()
        file = FileSnapshot(hash="test", path="nonexistent.txt")
        
        with mock.patch.object(FileSnapshot, 'full_path', new_callable=mock.PropertyMock) as mock_fp:
            mock_fp.return_value = "/nonexistent_path/nonexistent.txt"
            with pytest.raises(FileNotFoundError):
                parser.parse(file)


class TestParserRegistry:
    """Тесты ParserRegistry."""
    
    def test_get_parser_for_txt(self):
        """Находит парсер для .txt."""
        registry = build_parser_registry()
        parser = registry.get_parser("document.txt")
        
        assert parser is not None
        assert isinstance(parser, TXTParser)
    
    def test_get_parser_for_docx(self):
        """Находит парсер для .docx."""
        registry = build_parser_registry()
        parser = registry.get_parser("document.docx")
        
        assert parser is not None
    
    def test_get_parser_for_unknown_extension(self):
        """Возвращает None для неизвестного расширения."""
        registry = build_parser_registry()
        parser = registry.get_parser("document.xyz")
        
        assert parser is None
    
    def test_supported_extensions(self):
        """Возвращает список поддерживаемых расширений."""
        registry = build_parser_registry()
        extensions = registry.supported_extensions()
        
        assert ".txt" in extensions
        assert ".docx" in extensions
        assert ".pdf" in extensions
        assert ".pptx" in extensions
        assert ".xlsx" in extensions
