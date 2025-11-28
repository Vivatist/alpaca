#!/usr/bin/env python3
"""
Metadata Extractor - извлечение метаданных из PDF документов

Извлекает специфичные для PDF метаданные (автор, страницы, создатель и т.д.)
"""

from typing import Dict

try:
    import pypdf  # type: ignore
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

from utils.logging import get_logger

logger = get_logger("alpaca.parser.pdf_metadata_extractor")


def extract_pdf_metadata(file_path: str) -> Dict:
    """
    Извлечение СПЕЦИФИЧНЫХ для PDF метаданных
    
    Общие метаданные (file_name, file_path, file_size, etc.) добавляются в базовом классе.
    Здесь добавляем только специфичные для PDF данные.
    
    Args:
        file_path: Путь к PDF файлу
        
    Returns:
        Dict со специфичными метаданными (pages, author, subject, creator, producer, encrypted)
    """
    specific_metadata = {
        'pages': 0,
        'author': '',
        'subject': '',
        'creator': '',
        'producer': '',
        'encrypted': False
    }
    
    if not PYPDF_AVAILABLE:
        logger.warning("pypdf not available, returning empty metadata")
        return specific_metadata
    
    try:
        with open(file_path, 'rb') as f:
            pdf_reader = pypdf.PdfReader(f)
            
            # Базовая информация
            specific_metadata['pages'] = len(pdf_reader.pages)
            specific_metadata['encrypted'] = pdf_reader.is_encrypted
            
            # Метаданные из PDF Info
            if pdf_reader.metadata:
                info = pdf_reader.metadata
                
                # Конвертируем pypdf объекты в обычные строки
                author = info.get('/Author', '')
                specific_metadata['author'] = str(author) if author else ''
                
                subject = info.get('/Subject', '')
                specific_metadata['subject'] = str(subject) if subject else ''
                
                creator = info.get('/Creator', '')
                specific_metadata['creator'] = str(creator) if creator else ''
                
                producer = info.get('/Producer', '')
                specific_metadata['producer'] = str(producer) if producer else ''
            
            logger.debug(f"PDF-specific metadata | pages={specific_metadata['pages']} author={specific_metadata['author']}")
            
    except Exception as e:
        logger.warning(f"PDF-specific metadata extraction failed | file={file_path} error={type(e).__name__}: {e}")
    
    return specific_metadata
