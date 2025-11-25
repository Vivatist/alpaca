"""
Тесты для модуля парсинга (parser_word)
"""
import pytest
import os
from app.parsers.word.parser_word import parser_word_old_task


class TestParserWord:
    """Тесты парсинга DOCX файлов"""
    
    def test_parse_docx_file(self, temp_docx_file):
        """Тест парсинга реального DOCX файла"""
        file_info = {
            'hash': 'test_hash_123',
            'path': temp_docx_file
        }
        
        result = parser_word_old_task(file_info)
        
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0
        assert "Заголовок тестового документа" in result
        assert "первый параграф" in result
    
    def test_parse_nonexistent_file(self):
        """Тест парсинга несуществующего файла"""
        file_info = {
            'hash': 'test_hash_456',
            'path': '/tmp/nonexistent_file_12345.docx'
        }
        
        result = parser_word_old_task(file_info)
        
        # Должен вернуть пустую строку или None при ошибке
        assert result is None or result == ""
    
    def test_parse_empty_docx(self):
        """Тест парсинга пустого DOCX файла"""
        from docx import Document
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.docx', delete=False) as f:
            doc = Document()
            doc.save(f.name)
            temp_path = f.name
        
        try:
            file_info = {
                'hash': 'test_hash_empty',
                'path': temp_path
            }
            
            result = parser_word_old_task(file_info)
            
            # Пустой документ должен вернуть пустую строку
            assert result is not None
            assert isinstance(result, str)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_parse_docx_with_multiple_paragraphs(self):
        """Тест парсинга DOCX с несколькими параграфами"""
        from docx import Document
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.docx', delete=False) as f:
            doc = Document()
            paragraphs = [
                "Первый параграф документа.",
                "Второй параграф документа.",
                "Третий параграф документа.",
                "Четвёртый параграф документа.",
            ]
            for p in paragraphs:
                doc.add_paragraph(p)
            doc.save(f.name)
            temp_path = f.name
        
        try:
            file_info = {
                'hash': 'test_hash_multi',
                'path': temp_path
            }
            
            result = parser_word_old_task(file_info)
            
            assert result is not None
            assert len(result) > 0
            # Проверяем что все параграфы присутствуют
            for p in paragraphs:
                assert p in result
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
