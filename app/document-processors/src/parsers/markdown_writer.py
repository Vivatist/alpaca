#!/usr/bin/env python3
"""
Markdown Writer для ALPACA парсеров

Унифицированный модуль для сохранения результатов парсинга в Markdown файлы.
Используется всеми парсерами (PDF, Word, Mock) для единообразного формата вывода.

Возможности:
- Генерация YAML frontmatter с метаданными
- Сохранение в формате: {timestamp}_{safe_filename}.md
- Валидация путей и создание директорий
- Централизованное логирование операций сохранения
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
import logging

# Добавляем путь к shared модулям
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, '/app/shared/logging')

try:
    from alpaca_logger import setup_logger
    logger = setup_logger(os.getenv('SERVICE', 'markdown-writer'))
except ImportError:
    logger = logging.getLogger('markdown-writer')
    logging.basicConfig(level=logging.INFO)


class MarkdownWriter:
    """
    Утилита для сохранения результатов парсинга в Markdown файлы
    
    Обеспечивает единообразный формат вывода для всех парсеров:
    - YAML header с метаданными
    - Markdown контент
    - Стандартизированное именование файлов
    """
    
    def __init__(self, output_dir: str = "/volume_md"):
        """
        Инициализация writer'а
        
        Args:
            output_dir: Директория для сохранения .md файлов
        """
        self.output_dir = Path(output_dir)
        self.logger = logger
        
        # Создаём директорию если не существует
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Output directory ready | path={self.output_dir}")
        except Exception as e:
            self.logger.error(f"Failed to create output directory | path={self.output_dir} error={e}")
    
    def save(
        self, 
        parse_result: Dict, 
        original_filename: str,
        timestamp: Optional[datetime] = None
    ) -> Dict:
        """
        Сохранение результата парсинга в Markdown файл
        
        Args:
            parse_result: Результат парсинга с ключами:
                - yaml_header: str - YAML frontmatter
                - markdown: str - Markdown контент
                - success: bool - Статус парсинга
            original_filename: Оригинальное имя файла (для генерации .md имени)
            timestamp: Временная метка (если None - текущее время)
            
        Returns:
            Dict с результатом сохранения:
                - success: bool - Статус операции
                - markdown_file: str - Имя созданного файла
                - markdown_path: str - Полный путь к файлу
                - markdown_length: int - Размер контента
                - error: Optional[str] - Сообщение об ошибке
        """
        result = {
            'success': False,
            'markdown_file': '',
            'markdown_path': '',
            'markdown_length': 0,
            'error': None
        }
        
        try:
            # Проверка валидности parse_result
            if not parse_result.get('success', False):
                result['error'] = parse_result.get('error', 'Parse result indicates failure')
                self.logger.warning(f"Parse result not successful | file={original_filename} error={result['error']}")
                return result
            
            yaml_header = parse_result.get('yaml_header', '')
            markdown_content = parse_result.get('markdown', '')
            
            if not markdown_content:
                result['error'] = 'Empty markdown content'
                self.logger.warning(f"Empty markdown content | file={original_filename}")
                return result
            
            # Генерация имени файла
            if timestamp is None:
                timestamp = datetime.utcnow()
            
            md_filename = self._generate_filename(original_filename, timestamp)
            md_path = self.output_dir / md_filename
            
            # Сборка финального контента
            final_content = self._assemble_content(yaml_header, markdown_content)
            
            # Сохранение в файл
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(final_content)
            
            result['success'] = True
            result['markdown_file'] = md_filename
            result['markdown_path'] = str(md_path)
            result['markdown_length'] = len(markdown_content)
            
            self.logger.info(f"Markdown saved | file={md_filename} path={md_path} size={len(final_content)}")
            
        except Exception as e:
            result['error'] = str(e)
            result['success'] = False
            self.logger.error(f"Failed to save markdown | file={original_filename} error={type(e).__name__}: {e}")
        
        return result
    
    def _generate_filename(self, original_filename: str, timestamp: datetime) -> str:
        """
        Генерация имени .md файла с timestamp и безопасным именем
        
        Формат: {timestamp}_{safe_name}.md
        Пример: 20251028_143000_123_Dogovor_123.md
        
        Args:
            original_filename: Оригинальное имя файла
            timestamp: Временная метка
            
        Returns:
            Безопасное имя .md файла
        """
        # Timestamp в формате YYYYMMdd_HHmmss_fff (с миллисекундами)
        ts_str = timestamp.strftime('%Y%m%d_%H%M%S_%f')[:-3]
        
        # Безопасное имя из оригинального файла
        safe_name = self._make_safe_filename(original_filename)
        
        return f"{ts_str}_{safe_name}.md"
    
    def _make_safe_filename(self, filename: str) -> str:
        """
        Преобразование имени файла в безопасное для файловой системы
        
        - Удаление расширения
        - Замена пробелов на подчёркивания
        - Транслитерация кириллицы
        - Удаление небезопасных символов
        
        Args:
            filename: Оригинальное имя файла
            
        Returns:
            Безопасное имя для использования в пути
        """
        # Удаляем расширение
        name = Path(filename).stem
        
        # Простая транслитерация русских букв
        translit_map = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
            'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
            'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
            'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
            'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
            'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'Yo',
            'Ж': 'Zh', 'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M',
            'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U',
            'Ф': 'F', 'Х': 'H', 'Ц': 'Ts', 'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Sch',
            'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya'
        }
        
        # Применяем транслитерацию
        transliterated = ''.join(translit_map.get(c, c) for c in name)
        
        # Заменяем пробелы и небезопасные символы
        safe = transliterated.replace(' ', '_')
        safe = ''.join(c for c in safe if c.isalnum() or c in ('_', '-'))
        
        # Ограничиваем длину (максимум 100 символов)
        if len(safe) > 100:
            safe = safe[:100]
        
        # Если после очистки имя пустое - используем fallback
        if not safe:
            safe = "document"
        
        return safe
    
    def _assemble_content(self, yaml_header: str, markdown_content: str) -> str:
        """
        Сборка финального контента: YAML + Markdown
        
        Args:
            yaml_header: YAML frontmatter (с --- или без)
            markdown_content: Markdown текст
            
        Returns:
            Финальный контент для файла
        """
        # Проверяем наличие YAML разделителей
        if yaml_header and not yaml_header.startswith('---'):
            yaml_header = f"---\n{yaml_header}\n---"
        
        # Собираем контент
        if yaml_header:
            return f"{yaml_header}\n\n{markdown_content}"
        else:
            return markdown_content
    
    def save_from_parser_result(
        self,
        parse_result: Dict,
        file_path: str,
        timestamp: Optional[datetime] = None
    ) -> Dict:
        """
        Удобная обёртка для сохранения результата парсинга
        
        Автоматически извлекает имя файла из file_path
        
        Args:
            parse_result: Результат парсинга
            file_path: Путь к оригинальному файлу
            timestamp: Временная метка (опционально)
            
        Returns:
            Dict с результатом сохранения
        """
        original_filename = Path(file_path).name
        return self.save(parse_result, original_filename, timestamp)


# Singleton instance для использования в tasks
_markdown_writer = None

def get_markdown_writer(output_dir: str = "/volume_md") -> MarkdownWriter:
    """
    Получение singleton instance MarkdownWriter
    
    Args:
        output_dir: Директория для сохранения (по умолчанию /volume_md)
        
    Returns:
        MarkdownWriter instance
    """
    global _markdown_writer
    if _markdown_writer is None:
        _markdown_writer = MarkdownWriter(output_dir)
    return _markdown_writer
