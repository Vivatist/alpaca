"""
Реализации экстракторов метаданных.

=== НАЗНАЧЕНИЕ ===
Извлекает метаданные из документа для обогащения чанков
перед записью в векторную БД.

=== ЭКСПОРТЫ ===
- extract_metadata — основная функция (выбирается по settings)
- simple_extract — простой экстрактор (только расширение)
- llm_extract — LLM-экстрактор (расширение + анализ содержимого)

=== СИГНАТУРА ===
    def extract_metadata(file: FileSnapshot) -> Dict[str, Any]

=== ИСПОЛЬЗОВАНИЕ ===

    from core.application.document_processing.metaextractors import extract_metadata
    from core.domain.files import FileSnapshot

    file = FileSnapshot(path="doc.docx", hash="abc", status_sync="added", raw_text="...")
    
    metadata = extract_metadata(file)
    print(metadata)  # {"extension": "docx", "title": "...", ...}

=== ВЫБОР ЭКСТРАКТОРА ===
Выбор осуществляется через settings.METAEXTRACTOR_BACKEND:
- "simple" — только расширение файла
- "llm" — расширение + LLM-анализ (по умолчанию)

Дополнительные настройки для LLM:
- ENABLE_LLM_METAEXTRACTOR — включить LLM-извлечение
- LLM_METAEXTRACTOR_USE_REAL_LLM — использовать реальный LLM (иначе заглушка)
- LLM_METAEXTRACTOR_PREVIEW_LENGTH — длина текста для анализа
"""
from typing import Any, Dict

from settings import settings
from core.domain.files.models import FileSnapshot

from .simple_metaextractor import extract_metadata as simple_extract
from .llm_metaextractor import extract_metadata as llm_extract


def extract_metadata(file: FileSnapshot) -> Dict[str, Any]:
    """
    Извлекает метаданные из документа согласно настройкам.
    
    Использует settings.METAEXTRACTOR_BACKEND для выбора реализации:
    - "simple" — только расширение
    - "llm" — расширение + LLM-анализ
    """
    if settings.METAEXTRACTOR_BACKEND == "simple":
        return simple_extract(file)
    else:  # "llm" или любое другое значение
        return llm_extract(file)


__all__ = ["extract_metadata", "simple_extract", "llm_extract"]
