"""
Логирование для Ingest Service.

Использует contextvars для маркировки всех событий одного файла единым emoji.
"""

import logging
import sys
import random
from contextvars import ContextVar
from typing import Optional


# Контекстная переменная для хранения маркера текущего файла
file_marker: ContextVar[str] = ContextVar('file_marker', default='')

# Набор смайликов для маркировки файлов в логах
FILE_MARKERS = [
    "🍎", "🍊", "🍋", "🍇", "🍉", "🍓", "🫐", "🍑", "🥝", "🍍",
    "🥕", "🌽", "🥦", "🍆", "🌶️", "🥒", "🧄", "🧅", "🥔", "🍠",
    "🌸", "🌺", "🌻", "🌷", "🌹", "💐", "🪻", "🪷", "🌼", "💮",
    "⭐", "🌟", "💫", "✨", "🔮", "💎", "🎯", "🎲", "🎸", "🎺",
    "🐱", "🐶", "🐸", "🦊", "🐼", "🐨", "🦁", "🐯", "🐻", "🐰",
]


def set_file_marker(marker: Optional[str] = None) -> str:
    """
    Установить маркер для текущего файла.
    Если marker не указан - выбирает случайный.
    Возвращает установленный маркер.
    """
    if marker is None:
        marker = random.choice(FILE_MARKERS)
    file_marker.set(marker)
    return marker


def clear_file_marker() -> None:
    """Очистить маркер файла."""
    file_marker.set('')


def get_file_marker() -> str:
    """Получить текущий маркер файла."""
    return file_marker.get()


class MarkerFormatter(logging.Formatter):
    """Форматтер с поддержкой маркера файла из contextvars."""
    
    def format(self, record: logging.LogRecord) -> str:
        # Получаем маркер из контекста
        marker = file_marker.get()
        
        # Добавляем маркер к сообщению если он есть
        if marker:
            # Для ошибок добавляем ❌
            if record.levelno >= logging.ERROR:
                record.msg = f"❌{marker} {record.msg}"
            else:
                record.msg = f"{marker} {record.msg}"
        
        return super().format(record)


def setup_logging(level: str = "INFO") -> None:
    """Настроить логирование с поддержкой маркеров файлов."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Удаляем старые хендлеры
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Создаём хендлер с нашим форматтером
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(MarkerFormatter(
        fmt='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Получить логгер по имени."""
    return logging.getLogger(name)
