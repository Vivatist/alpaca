"""
FileManager - статический класс для управления файловыми операциями
Предоставляет утилиты для работы с файлами в контексте обработки документов
"""
import os
import hashlib
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from utils.logging import get_logger

logger = get_logger(__name__)


class FileManager:
    """Статический класс для файловых операций"""
    
   