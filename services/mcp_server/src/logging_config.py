"""
Настройка логирования для MCP Server.
"""

import logging
import sys


def setup_logging(level: str = "INFO"):
    """Настроить логирование."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s | %(levelname)-8s | %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)]
    )


def get_logger(name: str) -> logging.Logger:
    """Получить логгер."""
    return logging.getLogger(name)
