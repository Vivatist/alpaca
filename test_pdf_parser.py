#!/usr/bin/env python3
"""
Тест парсинга PDF с новым PyMuPDF парсером
"""
import sys
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent))

from app.parsers.pdf_parser_module.pdf_parser import PDFParser
from utils.file_manager import File
from utils.logging import setup_logging

setup_logging()

# Тестовый PDF файл
test_file = File(
    path="Приглашение на конференцию.pdf",
    hash="test_hash",
    status_sync="added"
)

parser = PDFParser(enable_ocr=False)
result = parser.parse(test_file)

print("="*60)
print("РЕЗУЛЬТАТ ПАРСИНГА:")
print("="*60)
print(result[:1000])  # Первые 1000 символов
print("="*60)
print(f"Общая длина: {len(result)} символов")
