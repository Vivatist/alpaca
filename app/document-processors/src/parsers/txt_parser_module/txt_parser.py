#!/usr/bin/env python3
"""
TXT Parser для RAG системы ALPACA

Парсер текстовых файлов (.txt) с автоопределением кодировки.

Pipeline:
    .txt → Encoding Detection → Markdown + YAML metadata

Возможности:
- Автоопределение кодировки (UTF-8, Windows-1251, etc.)
- Извлечение базовых метаданных (размер, дата модификации)
- Генерация YAML header с метаданными
- Экспорт в Markdown формат для RAG индексации
"""

import os
import sys
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

# Добавляем путь к базовому парсеру
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from base_parser import BaseParser

try:
    import chardet # type: ignore
    CHARDET_AVAILABLE = True
except ImportError:
    CHARDET_AVAILABLE = False


class TXTParser(BaseParser):
    """
    Парсер текстовых файлов с автоопределением кодировки
    
    Использует pipeline:
    1. Автоопределение кодировки (chardet)
    2. Чтение контента
    3. Извлечение метаданных (размер, даты)
    4. YAML header - метаданные для RAG
    """
    
    def __init__(self):
        """Инициализация парсера"""
        super().__init__("txt-parser")
        
        if not CHARDET_AVAILABLE:
            self.logger.warning("chardet not available, will use UTF-8 fallback")
    
    def parse(self, file_path: str, file_hash: Optional[str] = None) -> Dict:
        """
        Парсинг TXT файла в Markdown с метаданными
        
        Args:
            file_path: Путь к .txt файлу
            file_hash: Хэш файла от file-watcher (опционально)
            
        Returns:
            Dict с ключами:
                - markdown: str - Текст в Markdown формате
                - metadata: Dict - Метаданные документа
                - yaml_header: str - YAML header для документа
                - success: bool - Статус парсинга
                - error: Optional[str] - Сообщение об ошибке
        """
        result = {
            'markdown': '',
            'metadata': {},
            'yaml_header': '',
            'success': False,
            'error': None
        }
        
        try:
            if not os.path.exists(file_path):
                result['error'] = f"File not found: {file_path}"
                return result
            
            self.logger.info(f"Parsing TXT document | file={file_path}")
            
            # 1. Добавляем ОБЩИЕ метаданные (в базовом классе)
            common_metadata = self._add_common_metadata(file_path, file_hash)
            
            # 2. Определение кодировки
            encoding = self._detect_encoding(file_path)
            self.logger.info(f"Detected encoding | encoding={encoding}")
            
            # 3. Чтение контента
            try:
                with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                    content = f.read()
            except Exception as e:
                self.logger.warning(f"Failed to read with {encoding}, trying UTF-8 | error={e}")
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                encoding = 'utf-8'
            
            if not content or not content.strip():
                result['error'] = "Empty file content"
                self.logger.warning(f"Empty content | file={file_path}")
                return result
            
            # 4. Извлечение СПЕЦИФИЧНЫХ метаданных для TXT
            specific_metadata = self._extract_txt_specific_metadata(encoding, content)
            
            self.logger.info(f"Metadata extracted | lines={specific_metadata.get('lines', 0)} chars={specific_metadata.get('characters', 0)}")
            
            # 5. Форматирование в Markdown
            markdown_content = self._format_as_markdown(content, Path(file_path).name)
            result['markdown'] = markdown_content
            
            # 6. Объединяем все метаданные для результата
            result['metadata'] = {**common_metadata, **specific_metadata}
            
            # 7. Генерация YAML header с разделением общих и специфичных метаданных
            yaml_header = self._generate_yaml_header(
                common_metadata,
                specific_metadata,
                'txt'
            )
            result['yaml_header'] = yaml_header
            
            result['success'] = True
            
            self.logger.info(f"TXT parsed successfully | file={file_path} content_length={len(markdown_content)}")
            
        except Exception as e:
            result['error'] = str(e)
            result['success'] = False
            self.logger.error(f"TXT parsing failed | file={file_path} error={type(e).__name__}: {e}")
        
        return result
    
    def _detect_encoding(self, file_path: str) -> str:
        """
        Автоопределение кодировки файла
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            Название кодировки (utf-8, windows-1251, etc.)
        """
        if not CHARDET_AVAILABLE:
            return 'utf-8'
        
        try:
            # Читаем первые 10KB для определения кодировки
            with open(file_path, 'rb') as f:
                raw_data = f.read(10240)  # 10KB достаточно для определения
            
            if not raw_data:
                return 'utf-8'
            
            # Определяем кодировку
            detected = chardet.detect(raw_data)
            encoding = detected.get('encoding', 'utf-8')
            confidence = detected.get('confidence', 0.0)
            
            self.logger.debug(f"Encoding detection | encoding={encoding} confidence={confidence:.2f}")
            
            # Если уверенность низкая, используем UTF-8
            if confidence < 0.7:
                self.logger.warning(f"Low confidence in encoding detection | confidence={confidence:.2f} using_utf8=true")
                return 'utf-8'
            
            # Нормализация названий кодировок
            encoding_map = {
                'windows-1251': 'windows-1251',
                'cp1251': 'windows-1251',
                'utf-8': 'utf-8',
                'utf8': 'utf-8',
                'ascii': 'ascii',
                'iso-8859-1': 'latin-1',
                'latin-1': 'latin-1'
            }
            
            normalized = encoding_map.get(encoding.lower(), encoding)
            
            return normalized
            
        except Exception as e:
            self.logger.warning(f"Encoding detection failed | error={e} using_utf8=true")
            return 'utf-8'
    
    def _extract_txt_specific_metadata(self, encoding: str, content: str) -> Dict:
        """
        Извлечение СПЕЦИФИЧНЫХ для TXT метаданных
        
        Общие метаданные (file_name, file_path, file_size, etc.) добавляются в базовом классе.
        Здесь добавляем только специфичные для текстовых файлов данные.
        
        Args:
            encoding: Кодировка файла
            content: Содержимое файла
            
        Returns:
            Dict со специфичными метаданными
        """
        specific_metadata = {}
        
        try:
            # Специфичные для TXT метаданные
            specific_metadata['encoding'] = encoding
            specific_metadata['lines'] = len(content.splitlines())
            specific_metadata['characters'] = len(content)
            specific_metadata['words'] = len(content.split())
            
            self.logger.debug(f"TXT-specific metadata | encoding={encoding} lines={specific_metadata['lines']} words={specific_metadata['words']}")
            
        except Exception as e:
            self.logger.warning(f"Failed to extract TXT-specific metadata | error={type(e).__name__}: {e}")
        
        return specific_metadata
    
    def _format_as_markdown(self, content: str, filename: str) -> str:
        """
        Форматирование текста как Markdown
        
        Добавляет заголовок и сохраняет структуру текста
        
        Args:
            content: Текстовое содержимое
            filename: Имя файла для заголовка
            
        Returns:
            Markdown текст
        """
        # Заголовок документа
        title = Path(filename).stem.replace('_', ' ')
        markdown_lines = [f"# {title}", ""]
        
        # Разбиваем на абзацы (двойные переводы строк)
        paragraphs = content.split('\n\n')
        
        for para in paragraphs:
            # Убираем лишние пробелы, но сохраняем структуру
            para = para.strip()
            if para:
                markdown_lines.append(para)
                markdown_lines.append("")  # Пустая строка между абзацами
        
        return "\n".join(markdown_lines)
