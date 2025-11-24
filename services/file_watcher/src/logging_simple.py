"""
Упрощенная настройка логирования для file_watcher контейнера
"""

import logging
import sys
import os


def setup_logging():
    """Настраивает логирование для file_watcher"""
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    
    # Получаем корневой logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level))
    
    # Очищаем существующие handlers
    logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    
    # Формат логов
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """Возвращает logger с указанным именем"""
    return logging.getLogger(name)
