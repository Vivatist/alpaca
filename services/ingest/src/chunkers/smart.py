"""
Smart чанкер с LangChain RecursiveCharacterTextSplitter.
"""

from typing import List

from logging_config import get_logger
from contracts import FileSnapshot
from settings import settings

logger = get_logger("ingest.chunker.smart")


def smart_chunker(file: FileSnapshot) -> List[str]:
    """
    Smart чанкер с LangChain RecursiveCharacterTextSplitter.
    
    Особенности:
    - Рекурсивное разбиение с учётом структуры текста
    - Перекрытие (overlap) для сохранения контекста
    - Приоритет разделителей: параграфы → предложения → слова
    
    Args:
        file: FileSnapshot с заполненным raw_text
        
    Returns:
        Список чанков
    """
    text = file.raw_text or ""
    
    if not text.strip():
        logger.warning(f"Empty text for chunking | file={file.path}")
        return []
    
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )
        
        chunks = splitter.split_text(text)
        
        # Фильтруем пустые чанки
        chunks = [c.strip() for c in chunks if c.strip()]
        
        logger.info(f"Smart chunking complete | file={file.path} chunks={len(chunks)} overlap={settings.CHUNK_OVERLAP}")
        return chunks
        
    except ImportError:
        logger.warning("LangChain not available, falling back to simple chunker")
        from .simple import simple_chunker
        return simple_chunker(file)
    except Exception as e:
        logger.error(f"Smart chunking failed | error={e}")
        from .simple import simple_chunker
        return simple_chunker(file)
