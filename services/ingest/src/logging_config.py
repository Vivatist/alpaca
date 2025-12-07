"""
Логирование для Ingest Service.
"""

import logging
import sys
from typing import Optional


def setup_logging(level: str = "INFO") -> None:
    """Настроить логирование."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        stream=sys.stdout,
        force=True
    )


def get_logger(name: str) -> logging.Logger:
    """Получить логгер по имени."""
    return logging.getLogger(name)
