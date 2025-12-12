"""
Простой чанкер: разбивает текст на части фиксированного размера.
"""

from typing import List

from logging_config import get_logger
from contracts import FileSnapshot
from settings import settings

logger = get_logger("ingest.chunker.simple")


def simple_chunker(file: FileSnapshot) -> List[str]:
    """
    Простой чанкер: разбивает текст на части фиксированного размера.
    
    Логика:
    - Разбивает по абзацам (\\n\\n)
    - Собирает абзацы в чанки до достижения CHUNK_SIZE
    - Если абзац больше CHUNK_SIZE, разбивает по словам
    
    Args:
        file: FileSnapshot с заполненным raw_text
        
    Returns:
        Список чанков
    """
    text = file.raw_text or ""
    
    if not text.strip():
        logger.warning(f"Empty text for chunking")
        return []
    
    chunk_size = settings.CHUNK_SIZE
    chunks = []
    
    # Разбиваем по абзацам
    paragraphs = text.split('\n\n')
    current_chunk = ""
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        
        if len(current_chunk) + len(para) + 2 <= chunk_size:
            if current_chunk:
                current_chunk += "\n\n" + para
            else:
                current_chunk = para
        else:
            if current_chunk:
                chunks.append(current_chunk)
            
            # Если абзац больше chunk_size, разбиваем его
            if len(para) > chunk_size:
                words = para.split()
                current_chunk = ""
                for word in words:
                    if len(current_chunk) + len(word) + 1 <= chunk_size:
                        if current_chunk:
                            current_chunk += " " + word
                        else:
                            current_chunk = word
                    else:
                        if current_chunk:
                            chunks.append(current_chunk)
                        current_chunk = word
            else:
                current_chunk = para
    
    if current_chunk:
        chunks.append(current_chunk)
    
    logger.info(f"Simple chunking | chunks={len(chunks)}")
    return chunks
