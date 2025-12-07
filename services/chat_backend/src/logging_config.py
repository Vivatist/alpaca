"""
Настройка логирования для Chat Backend.
"""
import logging
import sys
from pythonjsonlogger import jsonlogger


_logging_configured = False


def setup_logging(level: str = "INFO") -> None:
    """Настраивает логирование."""
    global _logging_configured
    if _logging_configured:
        return
    
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    root_logger.handlers.clear()
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level.upper()))
    
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    
    # Тишина для шумных библиотек
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    
    _logging_configured = True


def get_logger(name: str) -> logging.Logger:
    """Получить logger."""
    return logging.getLogger(name)
