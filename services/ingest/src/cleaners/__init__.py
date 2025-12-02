"""
Клинеры для очистки текста.

Поддерживает последовательное применение клинеров через pipeline.
"""

import re
from typing import List, Callable

from logging_config import get_logger
from config import settings

logger = get_logger("ingest.cleaner")

# Тип клинера: (text) -> cleaned_text
CleanerFunc = Callable[[str], str]


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


# Реестр доступных клинеров
CLEANERS: dict[str, CleanerFunc] = {
    "simple": simple_cleaner,
    "stamps": stamps_cleaner,
}


def get_cleaner_pipeline(cleaner_names: List[str]) -> CleanerFunc:
    """
    Создаёт пайплайн клинеров для последовательного применения.
    
    Args:
        cleaner_names: Список имён клинеров в порядке применения
        
    Returns:
        Функция-клинер, применяющая все клинеры последовательно
    """
    cleaners = []
    for name in cleaner_names:
        if name in CLEANERS:
            cleaners.append(CLEANERS[name])
        else:
            logger.warning(f"Unknown cleaner: {name}, skipping")
    
    if not cleaners:
        logger.warning("No valid cleaners found, using identity function")
        return lambda x: x
    
    def pipeline(text: str) -> str:
        for cleaner in cleaners:
            text = cleaner(text)
        return text
    
    logger.info(f"Cleaner pipeline created | cleaners={cleaner_names}")
    return pipeline


def build_cleaner() -> CleanerFunc:
    """Создаёт клинер на основе настроек."""
    if not settings.ENABLE_CLEANER:
        logger.info("Cleaner disabled")
        return lambda x: x
    
    return get_cleaner_pipeline(settings.CLEANER_PIPELINE)


__all__ = [
    "simple_cleaner",
    "stamps_cleaner",
    "get_cleaner_pipeline",
    "build_cleaner",
    "CLEANERS",
]
