"""Тесты для simple_cleaner."""
import pytest
from core.domain.files.models import FileSnapshot
from core.application.document_processing.cleaners import clean_text


@pytest.fixture
def file_snapshot():
    """Фикстура FileSnapshot."""
    return FileSnapshot(
        hash="abc123def456",
        path="test_document.docx",
        size=1000,
        mtime=1234567890.0,
        status_sync="added",
        raw_text=None,
    )


class TestCleanTextBasic:
    """Базовые тесты очистки текста."""

    def test_removes_extra_spaces(self, file_snapshot):
        """Удаляет множественные пробелы."""
        file_snapshot.raw_text = "Hello    world   test"
        result = clean_text(file_snapshot)
        assert result == "Hello world test"

    def test_removes_extra_newlines(self, file_snapshot):
        """Нормализует переносы строк (макс. 2 подряд)."""
        file_snapshot.raw_text = "Line1\n\n\n\n\nLine2"
        result = clean_text(file_snapshot)
        assert result == "Line1\n\nLine2"

    def test_strips_lines(self, file_snapshot):
        """Удаляет пробелы в начале/конце строк."""
        file_snapshot.raw_text = "  Line1  \n  Line2  "
        result = clean_text(file_snapshot)
        assert result == "Line1\nLine2"

    def test_final_strip(self, file_snapshot):
        """Удаляет пробелы в начале/конце всего текста."""
        file_snapshot.raw_text = "\n\n  Hello  \n\n"
        result = clean_text(file_snapshot)
        assert result == "Hello"


class TestCleanTextEdgeCases:
    """Тесты граничных случаев."""

    def test_handles_empty_string(self, file_snapshot):
        """Обрабатывает пустую строку."""
        file_snapshot.raw_text = ""
        result = clean_text(file_snapshot)
        assert result == ""

    def test_handles_none(self, file_snapshot):
        """Обрабатывает None."""
        file_snapshot.raw_text = None
        result = clean_text(file_snapshot)
        assert result == ""

    def test_handles_whitespace_only(self, file_snapshot):
        """Обрабатывает текст только из пробелов."""
        file_snapshot.raw_text = "   \n\n   \t   "
        result = clean_text(file_snapshot)
        assert result == ""

    def test_preserves_single_newlines(self, file_snapshot):
        """Сохраняет одиночные переносы строк."""
        file_snapshot.raw_text = "Line1\nLine2\nLine3"
        result = clean_text(file_snapshot)
        assert result == "Line1\nLine2\nLine3"

    def test_preserves_double_newlines(self, file_snapshot):
        """Сохраняет двойные переносы (разделители параграфов)."""
        file_snapshot.raw_text = "Para1\n\nPara2\n\nPara3"
        result = clean_text(file_snapshot)
        assert result == "Para1\n\nPara2\n\nPara3"


class TestCleanTextControlChars:
    """Тесты удаления управляющих символов."""

    def test_removes_null_bytes(self, file_snapshot):
        """Удаляет NULL-байты."""
        file_snapshot.raw_text = "Hello\x00World"
        result = clean_text(file_snapshot)
        assert result == "HelloWorld"

    def test_removes_control_chars(self, file_snapshot):
        """Удаляет управляющие символы (кроме \\n и \\t)."""
        file_snapshot.raw_text = "Hello\x01\x02\x03World"
        result = clean_text(file_snapshot)
        assert result == "HelloWorld"

    def test_preserves_tabs(self, file_snapshot):
        """Сохраняет табуляции."""
        file_snapshot.raw_text = "Col1\tCol2\tCol3"
        result = clean_text(file_snapshot)
        assert result == "Col1\tCol2\tCol3"

    def test_preserves_newlines(self, file_snapshot):
        """Сохраняет переносы строк."""
        file_snapshot.raw_text = "Line1\nLine2"
        result = clean_text(file_snapshot)
        assert result == "Line1\nLine2"


class TestCleanTextUnicode:
    """Тесты нормализации Unicode."""

    def test_normalizes_nbsp(self, file_snapshot):
        """Нормализует неразрывные пробелы (U+00A0)."""
        file_snapshot.raw_text = "Hello\u00a0World"  # non-breaking space
        result = clean_text(file_snapshot)
        assert result == "Hello World"

    def test_normalizes_en_space(self, file_snapshot):
        """Нормализует EN SPACE (U+2002)."""
        file_snapshot.raw_text = "Hello\u2002World"
        result = clean_text(file_snapshot)
        assert result == "Hello World"

    def test_normalizes_em_space(self, file_snapshot):
        """Нормализует EM SPACE (U+2003)."""
        file_snapshot.raw_text = "Hello\u2003World"
        result = clean_text(file_snapshot)
        assert result == "Hello World"

    def test_normalizes_ideographic_space(self, file_snapshot):
        """Нормализует идеографический пробел (U+3000)."""
        file_snapshot.raw_text = "Hello\u3000World"
        result = clean_text(file_snapshot)
        assert result == "Hello World"

    def test_removes_zero_width_spaces(self, file_snapshot):
        """Удаляет zero-width пробелы (U+200B)."""
        file_snapshot.raw_text = "Hello\u200bWorld"
        result = clean_text(file_snapshot)
        assert result == "Hello World"

    def test_preserves_cyrillic(self, file_snapshot):
        """Сохраняет кириллицу."""
        file_snapshot.raw_text = "Привет мир"
        result = clean_text(file_snapshot)
        assert result == "Привет мир"

    def test_preserves_emoji(self, file_snapshot):
        """Сохраняет эмодзи."""
        file_snapshot.raw_text = "Hello 👋 World 🌍"
        result = clean_text(file_snapshot)
        assert result == "Hello 👋 World 🌍"


class TestCleanTextRealWorld:
    """Тесты на реальных примерах."""

    def test_document_with_mixed_issues(self, file_snapshot):
        """Документ с различными проблемами форматирования."""
        file_snapshot.raw_text = """  Заголовок документа  


    Первый параграф с    лишними   пробелами.


    
    
Второй параграф после множества пустых строк.

  Третий параграф с пробелами в начале.  """
        
        result = clean_text(file_snapshot)
        
        expected = """Заголовок документа

Первый параграф с лишними пробелами.

Второй параграф после множества пустых строк.

Третий параграф с пробелами в начале."""
        
        assert result == expected

    def test_table_like_content(self, file_snapshot):
        """Табличные данные с табуляциями."""
        file_snapshot.raw_text = "Name\tAge\tCity\nAlice\t30\tMoscow\nBob\t25\tParis"
        result = clean_text(file_snapshot)
        assert result == "Name\tAge\tCity\nAlice\t30\tMoscow\nBob\t25\tParis"

    def test_code_snippet(self, file_snapshot):
        """Код с отступами (отступы в начале строк удаляются)."""
        file_snapshot.raw_text = """def hello():
    print("Hello")
    return True"""
        
        result = clean_text(file_snapshot)
        # Отступы удаляются (strip каждой строки)
        expected = """def hello():
print("Hello")
return True"""
        
        assert result == expected


class TestCleanTextContract:
    """Тесты соответствия контракту Cleaner."""

    def test_returns_string(self, file_snapshot):
        """Возвращает строку."""
        file_snapshot.raw_text = "Test"
        result = clean_text(file_snapshot)
        assert isinstance(result, str)

    def test_accepts_file_snapshot(self, file_snapshot):
        """Принимает FileSnapshot."""
        file_snapshot.raw_text = "Test"
        # Не должно выбрасывать исключение
        result = clean_text(file_snapshot)
        assert result == "Test"

    def test_does_not_modify_original(self, file_snapshot):
        """Не модифицирует оригинальный FileSnapshot."""
        original_text = "Hello    World"
        file_snapshot.raw_text = original_text
        clean_text(file_snapshot)
        # raw_text не должен измениться внутри функции
        # (функция возвращает новую строку, а не модифицирует)
        assert file_snapshot.raw_text == original_text
