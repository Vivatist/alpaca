"""
settings - адаптер для совместимости с core/settings

Проксирует настройки из config.py в формате, ожидаемом парсерами из core/
"""
from config import settings

__all__ = ["settings"]
