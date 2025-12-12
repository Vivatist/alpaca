"""
Клинеры для очистки текста.

Поддерживает последовательное применение клинеров через pipeline.
"""

from typing import List, Callable

from logging_config import get_logger
from settings import settings

from .simple import simple_cleaner
from .stamps import stamps_cleaner
from .letterhead import letterhead_cleaner

logger = get_logger("ingest.cleaner")

# Тип клинера: (text) -> cleaned_text
CleanerFunc = Callable[[str], str]

# Реестр доступных клинеров
CLEANERS: dict[str, CleanerFunc] = {
    "simple": simple_cleaner,
    "stamps": stamps_cleaner,
    "letterhead": letterhead_cleaner,
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
    "letterhead_cleaner",
    "get_cleaner_pipeline",
    "build_cleaner",
    "CLEANERS",
]
