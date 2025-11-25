"""
Настройка логирования для приложения
"""

import logging
import sys
from pythonjsonlogger import jsonlogger

from settings import settings


def setup_logging():
    """Настраивает логирование для всего приложения"""
    # Получаем корневой logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
    
    # Очищаем существующие handlers
    logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
    
    # Формат логов
    if settings.ENVIRONMENT == 'production':
        # JSON формат для production
        formatter = jsonlogger.JsonFormatter(
            '%(asctime)s %(name)s %(levelname)s %(message)s',
            timestamp=True
        )
    else:
        # Читаемый формат для development
        formatter = logging.Formatter(
            settings.LOG_FORMAT,
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Уменьшаем уровень логирования для сторонних библиотек
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('asyncpg').setLevel(logging.WARNING)
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
    

def get_logger(name: str) -> logging.Logger:
    """Получить logger для модуля"""
    return logging.getLogger(name)
