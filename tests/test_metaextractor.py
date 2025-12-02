"""
Тесты для экстракторов метаданных
"""
import pytest
from unittest.mock import patch, MagicMock

from core.domain.files.models import FileSnapshot
from core.application.document_processing.metaextractors import (
    extract_metadata,
    simple_extract,
    llm_extract,
)
from core.application.document_processing.metaextractors.llm_metaextractor import (
    _parse_llm_response,
)


class TestSimpleMetaExtractor:
    """Тесты простого экстрактора"""
    
    def test_extract_docx_extension(self):
        """Тест извлечения расширения docx"""
        file = FileSnapshot(
            hash="test123",
            path="/docs/report.docx",
            status_sync="added"
        )
        
        metadata = simple_extract(file)
        
        assert metadata["extension"] == "docx"
    
    def test_extract_pdf_extension(self):
        """Тест извлечения расширения pdf"""
        file = FileSnapshot(
            hash="test123",
            path="document.PDF",
            status_sync="added"
        )
        
        metadata = simple_extract(file)
        
        assert metadata["extension"] == "pdf"  # в нижнем регистре
    
    def test_extract_no_extension(self):
        """Тест файла без расширения"""
        file = FileSnapshot(
            hash="test123",
            path="/docs/README",
            status_sync="added"
        )
        
        metadata = simple_extract(file)
        
        assert metadata["extension"] == ""
    
    def test_extract_complex_path(self):
        """Тест сложного пути с точками"""
        file = FileSnapshot(
            hash="test123",
            path="/docs/report.v2.final.xlsx",
            status_sync="added"
        )
        
        metadata = simple_extract(file)
        
        assert metadata["extension"] == "xlsx"


class TestLLMMetaExtractor:
    """Тесты LLM экстрактора"""
    
    def test_extract_without_raw_text(self):
        """Тест извлечения без текста — только расширение"""
        file = FileSnapshot(
            hash="test123",
            path="/docs/report.docx",
            status_sync="added",
            raw_text=None
        )
        
        with patch("core.application.document_processing.metaextractors.llm_metaextractor._call_llm") as mock_call:
            metadata = llm_extract(file)
            mock_call.assert_not_called()  # LLM не вызывался
        
        assert metadata["extension"] == "docx"
        assert "title" not in metadata
    
    def test_extract_with_llm_mock(self):
        """Тест с замоканным LLM"""
        file = FileSnapshot(
            hash="test123",
            path="/docs/report.docx",
            status_sync="added",
            raw_text="Important document about AI and machine learning."
        )
        
        mock_llm_response = '{"title": "AI Report", "summary": "About AI", "keywords": ["ai", "ml"]}'
        
        with patch("core.application.document_processing.metaextractors.llm_metaextractor._call_llm") as mock_call:
            mock_call.return_value = mock_llm_response
            metadata = llm_extract(file)
        
        assert metadata["extension"] == "docx"
        assert metadata["title"] == "AI Report"
        assert metadata["summary"] == "About AI"
        assert metadata["keywords"] == ["ai", "ml"]


class TestParseLLMResponse:
    """Тесты парсинга ответа LLM"""
    
    def test_parse_valid_json(self):
        """Тест парсинга валидного JSON"""
        response = '{"title": "Report", "summary": "A report", "keywords": ["ai", "ml"]}'
        
        result = _parse_llm_response(response)
        
        assert result["title"] == "Report"
        assert result["summary"] == "A report"
        assert result["keywords"] == ["ai", "ml"]
    
    def test_parse_json_with_markdown(self):
        """Тест парсинга JSON в markdown блоке"""
        response = '''```json
{"title": "Report", "summary": "A report", "keywords": ["ai"]}
```'''
        
        result = _parse_llm_response(response)
        
        assert result["title"] == "Report"
    
    def test_parse_invalid_json(self):
        """Тест парсинга невалидного JSON"""
        response = "Not a valid JSON"
        
        result = _parse_llm_response(response)
        
        assert result == {}
    
    def test_parse_none_response(self):
        """Тест парсинга None"""
        result = _parse_llm_response(None)
        
        assert result == {}


class TestMetaExtractorSelection:
    """Тесты выбора экстрактора через settings"""
    
    def test_simple_backend_selection(self):
        """Тест выбора simple экстрактора"""
        file = FileSnapshot(
            hash="test123",
            path="/docs/report.docx",
            status_sync="added"
        )
        
        with patch("core.application.document_processing.metaextractors.settings") as mock_settings:
            mock_settings.METAEXTRACTOR_BACKEND = "simple"
            metadata = extract_metadata(file)
        
        assert metadata["extension"] == "docx"
    
    def test_llm_backend_selection(self):
        """Тест выбора llm экстрактора"""
        file = FileSnapshot(
            hash="test123",
            path="/docs/report.pdf",
            status_sync="added"
        )
        
        with patch("core.application.document_processing.metaextractors.settings") as mock_settings:
            mock_settings.METAEXTRACTOR_BACKEND = "llm"
            with patch("core.application.document_processing.metaextractors.llm_metaextractor.settings") as llm_mock:
                llm_mock.ENABLE_LLM_METAEXTRACTOR = False
                metadata = extract_metadata(file)
        
        assert metadata["extension"] == "pdf"
