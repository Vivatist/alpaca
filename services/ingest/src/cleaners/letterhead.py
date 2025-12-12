"""
Letterhead Cleaner - удаление фирменных шапок документов с base64-изображениями.

Удаляет markdown-таблицы с логотипами компаний (base64 картинки),
которые появляются в начале документов после парсинга Word.
"""

import re
from logging_config import get_logger

logger = get_logger("ingest.cleaner.letterhead")


def letterhead_cleaner(text: str) -> str:
    """
    Удаление фирменных шапок с base64-изображениями.
    
    Очищает:
    - Markdown-таблицы содержащие base64-картинки ![](data:image/...)
    - Пустые таблицы | | | с разделителями
    - Мусорный текст перед шапкой (ТАЧа, георезоноанс и т.п.)
    """
    if not text:
        return ""
    
    original_len = len(text)
    
    # 1. Удаляем markdown-таблицы с base64-изображениями
    # Паттерн: | ... ![](data:image/...) ... |
    # Включает заголовки таблиц | --- | --- |
    base64_table_pattern = r'(?:^\|[^\n]*\|\s*\n)*^\|[^\n]*!\[\]\(data:image/[^\)]+\)[^\n]*\|\s*(?:\n|$)'
    text = re.sub(base64_table_pattern, '', text, flags=re.MULTILINE)
    
    # 2. Удаляем пустые таблицы-заголовки типа | | | и | --- | --- |
    empty_table_pattern = r'^\|\s*\|\s*\|\s*\n^\|\s*-+\s*\|\s*-+\s*\|\s*\n?'
    text = re.sub(empty_table_pattern, '', text, flags=re.MULTILINE)
    
    # 3. Удаляем одиночные строки с base64-картинками
    single_base64_pattern = r'^\s*!\[\]\(data:image/[^\)]+\)\s*\n?'
    text = re.sub(single_base64_pattern, '', text, flags=re.MULTILINE)
    
    # 4. Удаляем мусорные строки-артефакты OCR (короткие строки с кириллицей до первого осмысленного текста)
    # Например: "ТАЧа", "георезоноанс" - это артефакты распознавания логотипа
    # Удаляем только если они в начале документа (первые 500 символов)
    if len(text) > 0:
        # Находим первые 500 символов
        head = text[:500]
        # Удаляем короткие строки (до 20 символов) без пунктуации, которые выглядят как мусор
        head = re.sub(r'^[А-Яа-яёЁA-Za-z]{1,20}\s*\n', '', head, flags=re.MULTILINE)
        text = head + text[500:]
    
    # 5. Удаляем пустые строки в начале
    text = text.lstrip('\n')
    
    # 6. Нормализуем множественные переносы строк
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    cleaned_len = len(text)
    reduction = ((original_len - cleaned_len) / original_len * 100) if original_len > 0 else 0
    
    if reduction > 1:  # Логируем только если убрали больше 1%
        logger.debug(f"Letterhead cleaner | {original_len} → {cleaned_len} chars ({reduction:.1f}% reduced)")
    
    return text
