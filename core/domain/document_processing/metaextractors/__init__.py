"""
Доменный тип для экстракторов метаданных (MetaExtractor).

=== НАЗНАЧЕНИЕ ===
Определяет контракт для функций, извлекающих метаданные из документа.
Метаданные используются для обогащения чанков перед записью в БД.

=== СИГНАТУРА ===
    MetaExtractor = Callable[[FileSnapshot], dict[str, Any]]

Принимает: FileSnapshot (файл с path, hash, raw_text)
Возвращает: словарь метаданных

=== ИСПОЛЬЗОВАНИЕ ===

    from core.domain.document_processing.metaextractors import MetaExtractor
    from core.domain.files import FileSnapshot

    # Типизация экстрактора
    def my_extractor(file: FileSnapshot) -> dict[str, Any]:
        return {
            "extension": file.path.split(".")[-1],
            "size": file.size,
        }

    # Использовать в use-case
    extractor: MetaExtractor = my_extractor
    metadata = extractor(file)

=== РЕАЛИЗАЦИИ ===
- simple_metaextractor: только расширение файла
- llm_metaextractor: расширение + LLM-анализ содержимого
"""

from typing import Any, Callable, Dict
from core.domain.files.models import FileSnapshot

MetaExtractor = Callable[[FileSnapshot], Dict[str, Any]]

__all__ = ["MetaExtractor"]
