"""
Тесты для метаэкстракторов.
"""
import pytest
from contracts import FileSnapshot
from metaextractors import simple_extractor, EXTRACTORS, build_metaextractor


class TestSimpleExtractor:
    """Тесты simple_extractor."""
    
    def test_extracts_extension_docx(self):
        """Извлекает расширение .docx."""
        file = FileSnapshot(hash="test", path="/docs/report.docx", raw_text="")
        metadata = simple_extractor(file)
        
        assert metadata["extension"] == "docx"
    
    def test_extracts_extension_pdf(self):
        """Извлекает расширение .pdf."""
        file = FileSnapshot(hash="test", path="/docs/report.PDF", raw_text="")
        metadata = simple_extractor(file)
        
        assert metadata["extension"] == "pdf"
    
    def test_extracts_extension_txt(self):
        """Извлекает расширение .txt."""
        file = FileSnapshot(hash="test", path="readme.txt", raw_text="")
        metadata = simple_extractor(file)
        
        assert metadata["extension"] == "txt"
    
    def test_no_extension(self):
        """Файл без расширения."""
        file = FileSnapshot(hash="test", path="/docs/README", raw_text="")
        metadata = simple_extractor(file)
        
        assert metadata["extension"] == ""


class TestMetaExtractorRegistry:
    """Тесты реестра метаэкстракторов."""
    
    def test_registry_has_extractors(self):
        """Реестр содержит экстракторы."""
        assert "simple" in EXTRACTORS
        assert "llm" in EXTRACTORS
    
    def test_build_metaextractor_returns_callable(self):
        """build_metaextractor возвращает callable."""
        extractor = build_metaextractor()
        assert callable(extractor)
