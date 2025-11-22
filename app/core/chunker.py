"""
Чанкирование (разбиение) текста на фрагменты для векторизации
"""

from typing import List
from langchain_text_splitters import RecursiveCharacterTextSplitter
import logging

from settings import settings

logger = logging.getLogger(__name__)


class TextChunker:
    """Разбивает текст на чанки с перекрытием"""
    
    def __init__(self, chunk_size: int = None, chunk_overlap: int = None):
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP
        
        # Используем RecursiveCharacterTextSplitter из langchain
        # Он учитывает структуру текста (абзацы, предложения)
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            is_separator_regex=False,
            separators=[
                "\n\n",  # Двойной перенос (абзацы)
                "\n",    # Одинарный перенос
                ". ",    # Точка с пробелом (предложения)
                " ",     # Пробел (слова)
                "",      # Символы
            ]
        )
    
    def chunk_text(self, text: str) -> List[str]:
        """
        Разбивает текст на чанки
        
        Args:
            text: Исходный текст
        
        Returns:
            Список чанков
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for chunking")
            return []
        
        try:
            chunks = self.splitter.split_text(text)
            logger.info(
                f"Split text into {len(chunks)} chunks "
                f"(size={self.chunk_size}, overlap={self.chunk_overlap})"
            )
            return chunks
        except Exception as e:
            logger.error(f"Error chunking text: {e}", exc_info=True)
            return []
    
    def chunk_text_with_metadata(self, text: str, file_path: str = None) -> List[dict]:
        """
        Разбивает текст на чанки с метаданными
        
        Args:
            text: Исходный текст
            file_path: Путь к файлу (для метаданных)
        
        Returns:
            Список словарей [{'text': str, 'index': int, 'metadata': dict}, ...]
        """
        chunks = self.chunk_text(text)
        
        result = []
        for idx, chunk in enumerate(chunks):
            result.append({
                'text': chunk,
                'index': idx,
                'metadata': {
                    'chunk_index': idx,
                    'total_chunks': len(chunks),
                    'file_path': file_path,
                    'chunk_size': len(chunk)
                }
            })
        
        return result


def chunk_text(text: str, chunk_size: int = None, chunk_overlap: int = None) -> List[str]:
    """
    Удобная функция для чанкирования текста
    
    Args:
        text: Текст для разбиения
        chunk_size: Размер чанка в символах
        chunk_overlap: Перекрытие между чанками
    
    Returns:
        Список чанков
    """
    chunker = TextChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return chunker.chunk_text(text)
