"""
Доменный тип для клинеров (Cleaner).

=== НАЗНАЧЕНИЕ ===
Определяет контракт для функций, очищающих распарсенный текст
документа перед разбиением на чанки.

=== СИГНАТУРА ===
    Cleaner = Callable[[FileSnapshot], str]

Принимает: FileSnapshot с заполненным raw_text
Возвращает: очищенный текст (строка)

=== ИСПОЛЬЗОВАНИЕ ===

    from core.domain.document_processing.cleaners import Cleaner
    from core.domain.files import FileSnapshot

    # Типизация клинера
    def my_cleaner(file: FileSnapshot) -> str:
        text = file.raw_text or ""
        # Удалить лишние пробелы
        text = " ".join(text.split())
        return text

    # Использовать в use-case
    cleaner: Cleaner = my_cleaner
    cleaned_text = cleaner(file)
"""

from typing import Callable
from core.domain.files.models import FileSnapshot

# Контракт: принимает FileSnapshot, возвращает очищенный текст
Cleaner = Callable[[FileSnapshot], str]

__all__ = ["Cleaner"]