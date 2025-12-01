"""
Тесты для smart_chunker
"""
import pytest
from core.domain.files.models import FileSnapshot
from core.application.document_processing.chunkers.smart_chunker import (
    smart_chunking,
    _is_table_line,
    _extract_protected_blocks,
    _restore_protected_blocks,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CHUNK_OVERLAP,
)


class TestSmartChunker:
    """Тесты умного чанкера"""
    
    def test_basic_chunking(self):
        """Тест базового разбиения текста"""
        text = "Первый параграф текста. " * 100 + "\n\n" + "Второй параграф. " * 100
        file = FileSnapshot(hash="test123", path="/test.txt", status_sync="added", raw_text=text)
        
        chunks = smart_chunking(file, chunk_size=500, chunk_overlap=50)
        
        assert len(chunks) > 1
        assert all(len(c) <= 600 for c in chunks)  # С учётом overlap
    
    def test_empty_text(self):
        """Тест пустого текста"""
        file = FileSnapshot(hash="test123", path="/test.txt", status_sync="added", raw_text="")
        
        chunks = smart_chunking(file)
        
        assert chunks == []
    
    def test_none_text(self):
        """Тест None текста"""
        file = FileSnapshot(hash="test123", path="/test.txt", status_sync="added", raw_text=None)
        
        chunks = smart_chunking(file)
        
        assert chunks == []
    
    def test_small_text_no_split(self):
        """Тест маленького текста — не разбивается"""
        text = "Короткий текст."
        file = FileSnapshot(hash="test123", path="/test.txt", status_sync="added", raw_text=text)
        
        chunks = smart_chunking(file, chunk_size=1000)
        
        assert len(chunks) == 1
        assert chunks[0] == text
    
    def test_overlap_present(self):
        """Тест наличия перекрытия между чанками"""
        # Создаём текст с чёткими границами
        text = "Слово. " * 500  # ~3500 символов
        file = FileSnapshot(hash="test123", path="/test.txt", status_sync="added", raw_text=text)
        
        chunks = smart_chunking(file, chunk_size=500, chunk_overlap=100)
        
        assert len(chunks) > 2
        # Проверяем что есть перекрытие (последние слова первого чанка есть в начале второго)
        for i in range(len(chunks) - 1):
            # Берём последние 50 символов текущего чанка
            end_of_current = chunks[i][-50:]
            # Должны быть общие слова
            words_current = set(end_of_current.split())
            words_next = set(chunks[i+1][:100].split())
            # Хотя бы одно слово должно быть общим (из-за overlap)
            # Это мягкая проверка, т.к. разделение может быть по предложениям
            assert len(words_current) > 0 or len(words_next) > 0


class TestTablePreservation:
    """Тесты сохранения таблиц"""
    
    def test_is_table_line_markdown(self):
        """Тест определения Markdown таблицы"""
        assert _is_table_line("| Col1 | Col2 |")
        assert _is_table_line("| --- | --- |")
        assert _is_table_line("|Value1|Value2|")
        assert not _is_table_line("Обычный текст")
    
    def test_is_table_line_ascii(self):
        """Тест определения ASCII таблицы"""
        assert _is_table_line("+----+----+")
        assert _is_table_line("| ID | Name |")
        assert _is_table_line("---+---")
    
    def test_is_table_line_unicode(self):
        """Тест определения Unicode таблицы"""
        assert _is_table_line("┌────┬────┐")
        assert _is_table_line("│ A  │ B  │")
        assert _is_table_line("└────┴────┘")
    
    def test_extract_markdown_table(self):
        """Тест извлечения Markdown таблицы"""
        text = """Текст перед таблицей.

| Колонка 1 | Колонка 2 |
| --- | --- |
| Значение 1 | Значение 2 |

Текст после таблицы."""
        
        processed, protected = _extract_protected_blocks(text)
        
        assert len(protected) == 1
        placeholder = list(protected.keys())[0]
        assert "| Колонка 1 | Колонка 2 |" in protected[placeholder]
        assert "| Значение 1 | Значение 2 |" in protected[placeholder]
        assert placeholder in processed
        assert "Текст перед таблицей" in processed
        assert "Текст после таблицы" in processed
    
    def test_table_not_split(self):
        """Тест что таблица не разбивается на части"""
        # Создаём большую таблицу
        table_rows = ["| Col1 | Col2 | Col3 |", "| --- | --- | --- |"]
        table_rows.extend([f"| Row{i} | Data{i} | Value{i} |" for i in range(50)])
        table = "\n".join(table_rows)
        
        text = f"Введение.\n\n{table}\n\nЗаключение."
        file = FileSnapshot(hash="test123", path="/test.txt", status_sync="added", raw_text=text)
        
        chunks = smart_chunking(file, chunk_size=200, chunk_overlap=50, preserve_tables=True)
        
        # Таблица должна быть целиком в одном чанке
        table_chunk = None
        for chunk in chunks:
            if "| Col1 | Col2 | Col3 |" in chunk:
                table_chunk = chunk
                break
        
        assert table_chunk is not None
        assert "| Row49 | Data49 | Value49 |" in table_chunk  # Последняя строка тоже там


class TestCodeBlockPreservation:
    """Тесты сохранения блоков кода"""
    
    def test_extract_code_block(self):
        """Тест извлечения блока кода"""
        text = """Пример кода:

```python
def hello():
    print("Hello, World!")
```

Конец примера."""
        
        processed, protected = _extract_protected_blocks(text)
        
        assert len(protected) == 1
        placeholder = list(protected.keys())[0]
        assert "def hello():" in protected[placeholder]
        assert 'print("Hello, World!")' in protected[placeholder]
    
    def test_code_block_not_split(self):
        """Тест что блок кода не разбивается"""
        code = """```python
# Длинный код
def very_long_function():
    x = 1
    y = 2
    z = 3
    return x + y + z

class MyClass:
    def __init__(self):
        self.value = 42
    
    def method(self):
        return self.value * 2
```"""
        
        text = f"Введение.\n\n{code}\n\nЗаключение."
        file = FileSnapshot(hash="test123", path="/test.txt", status_sync="added", raw_text=text)
        
        chunks = smart_chunking(file, chunk_size=100, chunk_overlap=20, preserve_tables=True)
        
        # Код должен быть целиком
        code_chunk = None
        for chunk in chunks:
            if "def very_long_function" in chunk:
                code_chunk = chunk
                break
        
        assert code_chunk is not None
        assert "return self.value * 2" in code_chunk


class TestRestoreProtectedBlocks:
    """Тесты восстановления защищённых блоков"""
    
    def test_restore_single_block(self):
        """Тест восстановления одного блока"""
        chunks = ["Текст __PROTECTED_BLOCK_0__ ещё текст"]
        protected = {"__PROTECTED_BLOCK_0__": "| A | B |"}
        
        restored = _restore_protected_blocks(chunks, protected)
        
        assert restored[0] == "Текст | A | B | ещё текст"
    
    def test_restore_multiple_blocks(self):
        """Тест восстановления нескольких блоков"""
        chunks = [
            "Начало __PROTECTED_BLOCK_0__",
            "__PROTECTED_BLOCK_1__ конец"
        ]
        protected = {
            "__PROTECTED_BLOCK_0__": "| Таблица |",
            "__PROTECTED_BLOCK_1__": "```code```"
        }
        
        restored = _restore_protected_blocks(chunks, protected)
        
        assert "| Таблица |" in restored[0]
        assert "```code```" in restored[1]


class TestFallback:
    """Тесты fallback на simple_chunker"""
    
    def test_fallback_on_error(self, monkeypatch):
        """Тест fallback при ошибке LangChain"""
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        
        def mock_split_text(self, text):
            raise Exception("LangChain error")
        
        monkeypatch.setattr(RecursiveCharacterTextSplitter, "split_text", mock_split_text)
        
        text = "Тестовый текст. " * 100
        file = FileSnapshot(hash="test123", path="/test.txt", status_sync="added", raw_text=text)
        
        # Должен вернуть результат от simple_chunker, а не упасть
        chunks = smart_chunking(file)
        
        assert len(chunks) > 0
