"""
Stamps Cleaner - удаление штампов "Прошито, пронумеровано".
"""

import re
from logging_config import get_logger

logger = get_logger("ingest.cleaner.stamps")


def stamps_cleaner(text: str) -> str:
    """
    Удаление штампов типа "Прошито, пронумеровано" и нормализация underscores.
    
    Очищает:
    - Блоки "Прошито, пронумеровано на ___ листах. ФИО ___"
    - Экранированные underscores \_\_\_ → ___
    - Множественные underscores → единый блок
    """
    if not text:
        return ""
    
    original_len = len(text)
    
    # 1. Удаляем блоки "Прошито, пронумеровано..."
    # Паттерн захватывает весь блок включая подпись
    stamp_pattern = r'Прошито,?\s*пронумеровано\s*на\s*[_\\_\s\(\)А-Яа-яёЁ0-9]+листах\.?\s*[А-Яа-яёЁ\.\s]+[_\\_\s]+'
    text = re.sub(stamp_pattern, '', text, flags=re.IGNORECASE | re.MULTILINE)
    
    # 2. Заменяем экранированные underscores \_\_\_ на обычные ___
    text = re.sub(r'\\+_', '_', text)
    
    # 3. Нормализуем множественные underscores (3+ подряд) в единый блок
    text = re.sub(r'_{3,}', '___', text)
    
    # 4. Удаляем строки состоящие только из underscores и пробелов
    text = re.sub(r'^[\s_]+$', '', text, flags=re.MULTILINE)
    
    # 5. Удаляем образовавшиеся пустые строки
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()
    
    cleaned_len = len(text)
    reduction = ((original_len - cleaned_len) / original_len * 100) if original_len > 0 else 0
    
    if reduction > 0:
        logger.debug(f"Stamps cleaner | {original_len} → {cleaned_len} chars ({reduction:.1f}% reduced)")
    
    return text
