"""Custom chunker для разбивки текста на чанки"""
from typing import List
from utils.logging import get_logger
from alpaca.domain.files.models import FileSnapshot

logger = get_logger("alpaca.chunker")


def chunking(file: FileSnapshot) -> List[str]:
    """Разбивка текста на чанки
    
    Args:
        file_path: Путь к файлу (для логов)
        text: Распарсенный текст документа
        
    Returns:
        List[str]: список чанков
    """
    try:
        logger.info(f"🔪 Chunking: {file.path}")
        
        chunks = []
        max_chunk_size = 1000  # символов
        paragraphs = (file.raw_text or "").split('\n\n')
        
        current_chunk = ""
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            if len(current_chunk) + len(para) > max_chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = para
            else:
                current_chunk += "\n\n" + para if current_chunk else para
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        logger.info(f"✅ Created {len(chunks)} chunks for {file.path}")
        return chunks
        
    except Exception as e:
        logger.error(f"Failed to chunk text | file={file.path} error={e}")
        return []
