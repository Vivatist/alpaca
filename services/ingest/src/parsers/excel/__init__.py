"""
Excel Parser — модуль для обработки таблиц.

=== НАЗНАЧЕНИЕ ===
Извлечение текста из .xls и .xlsx файлов:
- Данные из всех листов
- Автоопределение шапок таблиц
- Конвертация в Markdown-таблицы

=== СТЕК ТЕХНОЛОГИЙ ===
- openpyxl — парсинг .xlsx
- xlrd — парсинг старых .xls

=== ЭКСПОРТЫ ===
- ExcelParser — основной парсер

=== ИСПОЛЬЗОВАНИЕ ===

    from contracts import FileSnapshot

    parser = ExcelParser()
    file = FileSnapshot(path="data.xlsx", hash="abc123")
    text = parser.parse(file)

    # Результат в формате Markdown-таблиц:
    # | Column1 | Column2 |
    # |---------|--------|
    # | value1  | value2 |
"""

from .excel_parser import ExcelParser

__all__ = ["ExcelParser"]
