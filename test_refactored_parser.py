#!/usr/bin/env python3
"""
Тест рефакторенного word_parser с реальным файлом OCR
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "app" / "parsers"))

from app.parsers.word_parser_module.word_parser import WordParser
from utils.file_manager import File

# Тестовый файл
test_file_path = "/home/alpaca/monitored_folder/1.ТестOCR.docx"

# Создаем простой mock объект File
class MockFile:
    def __init__(self, path):
        self.path = path
        self.hash = "test_hash"

file_obj = MockFile(test_file_path)

# Инициализируем парсер с OCR
parser = WordParser(enable_ocr=True, ocr_strategy="auto")

# Парсим
print(f"🍎 Парсинг файла: {test_file_path}")
result = parser.parse(file_obj)

# Результаты
print(f"\n✅ Парсинг завершён")
print(f"📊 Длина результата: {len(result)} символов")
print(f"\n{'='*60}")
print("Первые 500 символов:")
print(result[:500])
print(f"{'='*60}")
