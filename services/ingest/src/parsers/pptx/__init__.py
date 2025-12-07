"""
PowerPoint Parser — модуль для обработки презентаций.

=== НАЗНАЧЕНИЕ ===
Извлечение текста из .ppt и .pptx файлов:
- Текст со слайдов
- Заметки докладчика
- Таблицы

=== СТЕК ТЕХНОЛОГИЙ ===
- python-pptx — основной парсинг
- Unstructured API — fallback для сложных случаев

=== ЭКСПОРТЫ ===
- PowerPointParser — основной парсер
- PptxParser — алиас для совместимости

=== ИСПОЛЬЗОВАНИЕ ===

    from contracts import FileSnapshot

    parser = PowerPointParser()
    file = FileSnapshot(path="presentation.pptx", hash="abc123")
    text = parser.parse(file)
    print(f"Extracted {len(text)} chars from slides")
"""

from .pptx_parser import PowerPointParser, PptxParser

__all__ = ["PowerPointParser", "PptxParser"]
