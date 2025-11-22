"""
Тесты для chunker
"""

import pytest
from app.core.chunker import TextChunker, chunk_text


def test_chunker_basic():
    """Тест базового чанкирования"""
    text = "Это первое предложение. " * 100  # Большой текст
    
    chunker = TextChunker(chunk_size=100, chunk_overlap=20)
    chunks = chunker.chunk_text(text)
    
    assert len(chunks) > 1, "Текст должен быть разбит на несколько чанков"
    assert all(len(chunk) <= 120 for chunk in chunks), "Чанки не должны превышать размер"


def test_chunker_empty():
    """Тест с пустым текстом"""
    chunker = TextChunker()
    
    assert chunker.chunk_text("") == []
    assert chunker.chunk_text("   ") == []
    assert chunker.chunk_text(None) == []


def test_chunker_short_text():
    """Тест с коротким текстом"""
    text = "Короткий текст"
    chunker = TextChunker(chunk_size=1000)
    chunks = chunker.chunk_text(text)
    
    assert len(chunks) == 1, "Короткий текст должен быть одним чанком"
    assert chunks[0] == text


def test_chunk_text_function():
    """Тест удобной функции chunk_text"""
    text = "Тестовый текст. " * 50
    chunks = chunk_text(text, chunk_size=100, chunk_overlap=20)
    
    assert isinstance(chunks, list)
    assert len(chunks) > 0


def test_chunker_with_metadata():
    """Тест чанкирования с метаданными"""
    text = "Текст для чанкирования. " * 50
    chunker = TextChunker(chunk_size=100, chunk_overlap=20)
    
    result = chunker.chunk_text_with_metadata(text, file_path="test.txt")
    
    assert len(result) > 0
    assert all('text' in item for item in result)
    assert all('index' in item for item in result)
    assert all('metadata' in item for item in result)
    assert result[0]['metadata']['file_path'] == "test.txt"


def test_chunker_overlap():
    """Тест перекрытия чанков"""
    text = "Первое предложение. Второе предложение. Третье предложение. Четвёртое предложение."
    
    chunker = TextChunker(chunk_size=50, chunk_overlap=10)
    chunks = chunker.chunk_text(text)
    
    # Проверяем что есть перекрытие между чанками
    if len(chunks) > 1:
        # Ищем общие слова между соседними чанками
        for i in range(len(chunks) - 1):
            words1 = set(chunks[i].split())
            words2 = set(chunks[i+1].split())
            # Должны быть общие слова из-за overlap
            assert len(words1 & words2) > 0, "Должно быть перекрытие между чанками"
