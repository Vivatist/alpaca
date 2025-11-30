#!/usr/bin/env python3
"""
Base Parser для RAG системы ALPACA

Базовый класс для всех парсеров документов с общей функциональностью.
"""

import sys
import os
import yaml
from pathlib import Path
from typing import Dict, Optional, TYPE_CHECKING
from datetime import datetime
from abc import ABC, abstractmethod


from utils.logging import get_logger

if TYPE_CHECKING:
    from alpaca.domain.files.models import FileSnapshot


class BaseParser(ABC):
    """Базовый класс. Реализует шаблон Template Method для парсинга."""

    def __init__(self, parser_name: str):
        self.logger = get_logger(f"alpaca.parser.{parser_name}")

    def parse(self, file: 'FileSnapshot') -> str:
        """Финальный метод: вызывает реализацию `_parse` и гарантирует непустой текст."""
        text = self._parse(file)
        return self._ensure_text(text, file)

    @abstractmethod
    def _parse(self, file: 'FileSnapshot') -> str:
        """Реализация парсинга в наследнике."""
        raise NotImplementedError
    
    def _add_common_metadata(self, file_path: str, file_hash: Optional[str] = None) -> Dict:
        """
        Добавление общих метаданных для всех типов документов
        
        Эти метаданные одинаковы для всех парсеров:
        - file_name: имя файла
        - file_path: полный путь
        - file_hash: хэш от file-watcher (если передан)
        - file_size: размер в байтах
        - file_modified: дата последней модификации
        - file_created: дата создания (если доступна)
        
        Args:
            file_path: Путь к файлу
            file_hash: Хэш от file-watcher (опционально)
            
        Returns:
            Dict с общими метаданными
        """
        common_metadata = {}
        
        try:
            path = Path(file_path)
            
            # Базовая информация о файле
            common_metadata['file_name'] = path.name
            common_metadata['file_path'] = str(path.absolute())
            
            # Хэш от file-watcher (если передан)
            if file_hash:
                common_metadata['file_hash'] = file_hash
            
            # Размер файла
            if path.exists():
                stat = path.stat()
                common_metadata['file_size'] = stat.st_size
                
                # Даты модификации и создания
                common_metadata['file_modified'] = datetime.fromtimestamp(stat.st_mtime).isoformat()
                common_metadata['file_created'] = datetime.fromtimestamp(stat.st_ctime).isoformat()
            
            self.logger.debug(f"Common metadata added | file={path.name} hash={file_hash} size={common_metadata.get('file_size', 0)}")
            
        except Exception as e:
            self.logger.warning(f"Failed to add common metadata | file={file_path} error={type(e).__name__}: {e}")
            # Минимальные метаданные в случае ошибки
            common_metadata['file_name'] = Path(file_path).name
            common_metadata['file_path'] = file_path
            if file_hash:
                common_metadata['file_hash'] = file_hash
        
        return common_metadata
    
    def save_to_markdown_file(self, parse_result: Dict, output_path: str) -> bool:
        """
        Сохранение результата парсинга в Markdown файл
        
        Args:
            parse_result: Результат parse()
            output_path: Путь для сохранения .md файла
            
        Returns:
            bool: True если успешно
        """
        if not parse_result['success']:
            return False
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(parse_result['yaml_header'])
                f.write("\n")
                f.write(parse_result['markdown'])
            
            self.logger.info(f"Markdown saved | path={output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving markdown | path={output_path} error={type(e).__name__}: {e}")
            return False

    def _ensure_text(self, text: Optional[str], file: 'FileSnapshot') -> str:
        """Валидация результата парсинга — запрещены пустые строки."""
        if text is None:
            raise ValueError(
                f"Parser {self.__class__.__name__} returned None | file={getattr(file, 'path', 'unknown')}"
            )
        if not text.strip():
            raise ValueError(
                f"Parser {self.__class__.__name__} returned empty text | file={getattr(file, 'path', 'unknown')}"
            )
        return text
    
    def _generate_yaml_header(
        self,
        common_metadata: Dict,
        specific_metadata: Dict,
        document_type: str
    ) -> str:
        """
        Генерация YAML header для RAG индексации
        
        НОВАЯ ЛОГИКА: разделение общих и специфичных метаданных
        - Общие метаданные (file_name, file_path, file_hash, etc.) добавляются в базовом классе
        - Специфичные метаданные (encoding для txt, pages для pdf, etc.) добавляются в наследниках
        
        Args:
            common_metadata: Общие метаданные от _add_common_metadata()
            specific_metadata: Специфичные метаданные от наследников
            document_type: Тип документа (word, pdf, txt, mock, etc)
            
        Returns:
            YAML header как строка
        """
        # Начинаем с системных полей
        yaml_data = {
            'document_type': document_type,
            'parsed_date': datetime.utcnow().isoformat() + 'Z',
            'parser': f'alpaca-{document_type}-parser',
        }
        
        # Добавляем ОБЩИЕ метаданные (file_name, file_path, file_hash, file_size, etc.)
        yaml_data.update(common_metadata)
        
        # Добавляем СПЕЦИФИЧНЫЕ метаданные (encoding, pages, etc.)
        yaml_data.update(specific_metadata)
        
        # Генерируем YAML без переноса длинных строк
        # Используем кастомный Dumper который не разбивает строки
        class NoLinewrapDumper(yaml.SafeDumper):
            def write_line_break(self, data=None):
                super().write_line_break(data)
                
            def choose_scalar_style(self):
                return '"' if '\n' not in self.event.value and len(self.event.value) > 80 else super().choose_scalar_style()
        
        yaml_str = yaml.dump(yaml_data, Dumper=NoLinewrapDumper, allow_unicode=True, default_flow_style=False, sort_keys=False, width=999999)
        
        return f"---\n{yaml_str}---\n"
