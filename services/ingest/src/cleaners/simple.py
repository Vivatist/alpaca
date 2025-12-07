"""
Simple Cleaner - базовая очистка текста.
"""

import re
from logging_config import get_logger

logger = get_logger("ingest.cleaner.simple")


def simple_cleaner(text: str) -> str:
    """
    Базовый клинер: нормализация пробелов, Unicode, control chars.
    """
    if not text:
        return ""
    
    original_len = len(text)
    
    # 1. Удаляем управляющие символы (кроме \n и \t)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    
    # 2. Нормализуем Unicode пробелы
    text = re.sub(r'[\u00a0\u2000-\u200b\u202f\u205f\u3000]', ' ', text)
    
    # 3. Удаляем множественные пробелы
    text = re.sub(r' +', ' ', text)
    
    # 4. Удаляем пробелы в начале/конце строк
    text = '\n'.join(line.strip() for line in text.split('\n'))
    
    # 5. Удаляем множественные переносы строк (больше 2)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # 6. Финальный strip
    text = text.strip()
    
    cleaned_len = len(text)
    reduction = ((original_len - cleaned_len) / original_len * 100) if original_len > 0 else 0
    
    logger.debug(f"Simple cleaner | {original_len} → {cleaned_len} chars ({reduction:.1f}% reduced)")
    
    return text
