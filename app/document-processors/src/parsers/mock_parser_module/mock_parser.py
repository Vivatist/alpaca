#!/usr/bin/env python3
"""
Mock Parser для стресс-тестирования системы обработки документов
Имитирует парсинг с задержкой и копированием файлов
"""
import sys
import shutil
import time
import random
from pathlib import Path
from typing import Dict, Optional

# Добавляем путь к базовому парсеру
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, '/app/src/parsers')
from base_parser import BaseParser

# Импорт конфига
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent.parent / 'shared' / 'config'))
sys.path.insert(0, '/app/shared/config')
from config_loader import ConfigLoader


class MockParser(BaseParser):
    """
    Mock парсер для имитации обработки документов
    Применяет задержку с распределением Гаусса и копирует файл с префиксом
    """
    
    def __init__(self):
        super().__init__("mock-parser")
        
        config = ConfigLoader.load_full_config()
        mock_config = config.get('document_processors', {}).get('mock_parser', {})
        delay_config = mock_config.get('delay', {})
        
        self.output_path = Path(mock_config.get('output_path', '/volume_md'))
        self.prefix = mock_config.get('prefix', 'mock_')
        self.delay_mean = delay_config.get('mean', 5.5)
        self.delay_std = delay_config.get('std', 2.0)
        self.delay_min = delay_config.get('min', 1.0)
        self.delay_max = delay_config.get('max', 10.0)
        
        self.output_path.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"MockParser initialized | output={self.output_path} prefix={self.prefix} delay={self.delay_min}-{self.delay_max}s")
    
    def parse(self, file_path: str, file_hash: Optional[str] = None) -> Dict:
        """
        Имитация парсинга документа
        
        Args:
            file_path: Путь к файлу
            file_hash: Хэш файла от file-watcher (опционально)
            
        Returns:
            Dict с результатами парсинга
        """
        result = {
            'markdown': '',
            'metadata': {},
            'yaml_header': '',
            'success': False,
            'error': None,
            'original_file': file_path
        }
        
        try:
            path = Path(file_path)
            
            if not path.exists():
                self.logger.warning(f"File not found | file={file_path}")
                result['error'] = 'File not found'
                return result
            
            # Задержка с Гауссовым распределением
            delay = random.gauss(self.delay_mean, self.delay_std)
            delay = max(self.delay_min, min(delay, self.delay_max))

            self.logger.warning(f"Mock processing | file={path.name} delay={delay:.2f}s")
            time.sleep(delay)
            
            # 1. Добавляем ОБЩИЕ метаданные (в базовом классе)
            common_metadata = self._add_common_metadata(file_path, file_hash)
            
            # 2. Специфичные для mock метаданные
            specific_metadata = {
                'processing_delay_seconds': round(delay, 2),
                'mock_processor': True
            }
            
            # 3. Простой markdown контент
            markdown = f"# Mock Processed: {path.name}\n\n"
            markdown += f"Файл обработан mock парсером с задержкой {delay:.2f} секунд.\n\n"
            markdown += f"- **Размер файла**: {common_metadata.get('file_size', 0)} байт\n"
            markdown += f"- **Исходный путь**: {file_path}\n"
            if file_hash:
                markdown += f"- **Хэш файла**: {file_hash}\n"
            
            result['markdown'] = markdown
            
            # 4. Объединяем все метаданные для результата
            result['metadata'] = {**common_metadata, **specific_metadata}
            
            # 5. Генерация YAML header с разделением общих и специфичных метаданных
            yaml_header = self._generate_yaml_header(
                common_metadata,
                specific_metadata,
                'mock'
            )
            result['yaml_header'] = yaml_header
            
            result['success'] = True
            
            self.logger.info(f"Mock processing complete | file={path.name} duration={delay:.2f}s")
            
        except Exception as e:
            result['error'] = str(e)
            result['success'] = False
            self.logger.error(f"Mock processing failed | file={file_path} error={type(e).__name__}: {e}")
        
        return result
    
    def save_to_markdown_file(self, parse_result: Dict, output_path: str) -> bool:
        """
        Сохранение результата с копированием исходного файла
        
        Args:
            parse_result: Результат parse()
            output_path: Путь для сохранения .md файла (игнорируется, используется имя из исходного файла)
            
        Returns:
            bool: True если успешно
        """
        if not parse_result['success']:
            return False
        
        try:
            # Получаем исходный файл
            original_file = Path(parse_result['original_file'])
            
            # Создаем новое имя с префиксом mock-
            new_name = f"{self.prefix}{original_file.name}"
            target_path = self.output_path / new_name
            
            # Копируем исходный файл
            shutil.copy2(str(original_file), str(target_path))
            
            self.logger.warning(f"Mock file saved | source={original_file.name} target={new_name}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving mock file: {e}")
            return False
