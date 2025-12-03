"""
Чанкеры для разбиения текста на части.

Поддерживает:
- simple: простое разбиение по размеру
- smart: LangChain RecursiveCharacterTextSplitter с overlap
"""

from typing import List

from logging_config import get_logger
from contracts import FileSnapshot, Chunker
from settings import settings

logger = get_logger("ingest.chunker")


def simple_chunker(file: FileSnapshot) -> List[str]:
    """
    Простой чанкер: разбивает текст на части фиксированного размера.
    
    Args:
        file: FileSnapshot с заполненным raw_text
        
    Returns:
        Список чанков
    """
    text = file.raw_text or ""
    
    if not text.strip():
        logger.warning(f"Empty text for chunking | file={file.path}")
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
    
    logger.info(f"Simple chunking complete | file={file.path} chunks={len(chunks)}")
    return chunks


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
        return simple_chunker(file)
    except Exception as e:
        logger.error(f"Smart chunking failed | error={e}")
        return simple_chunker(file)


def build_chunker() -> Chunker:
    """Создаёт чанкер на основе настроек."""
    backend = settings.CHUNKER_BACKEND
    
    if backend == "smart":
        logger.info(f"Using smart chunker | size={settings.CHUNK_SIZE} overlap={settings.CHUNK_OVERLAP}")
        return smart_chunker
    else:
        logger.info(f"Using simple chunker | size={settings.CHUNK_SIZE}")
        return simple_chunker


__all__ = [
    "simple_chunker",
    "smart_chunker",
    "build_chunker",
]
