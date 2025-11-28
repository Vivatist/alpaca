#!/usr/bin/env python3
"""
Тест рефакторенного txt_parser с реальным файлом
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "app" / "parsers"))

from app.parsers.txt_parser_module.txt_parser import TXTParser

# Создаём тестовый файл
test_content = """Тестовый документ

Это первый параграф с русским текстом.
Проверка кодировки UTF-8.

Это второй параграф.
Содержит несколько строк текста.

Третий параграф - последний."""

# Создаём временный файл
with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
    f.write(test_content)
    test_file_path = f.name

# Создаём mock объект File
class MockFile:
    def __init__(self, path):
        self.path = path
        self.hash = "test_hash"

file_obj = MockFile(test_file_path)

# Инициализируем парсер
parser = TXTParser()

# Парсим
print(f"🍎 Парсинг файла: {test_file_path}")
result = parser.parse(file_obj)

# Результаты
print(f"\n✅ Парсинг завершён")
print(f"📊 Длина результата: {len(result)} символов")
print(f"\n{'='*60}")
print("Результат:")
print(result)
print(f"{'='*60}")

# Очистка
import os
os.unlink(test_file_path)
