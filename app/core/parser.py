"""
Парсинг документов через Unstructured API
Портировано из alpaca-n8n/parsing
"""

from pathlib import Path
from typing import Literal, Optional
import httpx
import logging

from settings import settings

logger = logging.getLogger(__name__)


class DocumentParser:
    """Парсинг документов различных форматов через Unstructured API"""
    
    def __init__(
        self,
        unstructured_url: str = None,
        timeout: int = None,
        strategy: str = None
    ):
        self.unstructured_url = unstructured_url or settings.UNSTRUCTURED_URL
        self.timeout = timeout or settings.UNSTRUCTURED_TIMEOUT
        self.strategy = strategy or settings.UNSTRUCTURED_STRATEGY
    
    async def parse_file(
        self,
        file_path: Path,
        output_format: Literal['text', 'markdown'] = 'text'
    ) -> Optional[str]:
        """
        Парсит файл через Unstructured API
        
        Args:
            file_path: Полный путь к файлу
            output_format: Формат вывода - 'text' или 'markdown'
        
        Returns:
            Распарсенный текст или None при ошибке
        """
        logger.info(f"Parsing file: {file_path}, format: {output_format}")
        
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return None
        
        if not file_path.is_file():
            logger.error(f"Path is not a file: {file_path}")
            return None
        
        try:
            # Читаем файл
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            # Подготавливаем запрос к Unstructured API
            files = {
                'files': (file_path.name, file_content)
            }
            
            data = {
                'strategy': self.strategy,
                'coordinates': 'false',
                'encoding': 'utf-8',
                'output_encoding': 'utf-8',
                'ocr_languages': 'rus+eng',
                'hi_res_model_name': 'yolox',
                'pdf_infer_table_structure': 'true',
                'skip_infer_table_types': '[]',
            }
            
            logger.debug(f"Calling Unstructured API: {self.unstructured_url}/general/v0/general")
            
            # Отправляем запрос к Unstructured API
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.unstructured_url}/general/v0/general",
                    files=files,
                    data=data
                )
                
                if response.status_code != 200:
                    logger.error(
                        f"Unstructured API error: {response.status_code} - {response.text}"
                    )
                    return None
                
                # Явно указываем кодировку UTF-8 для ответа
                response.encoding = 'utf-8'
                
                # Парсим результат
                result = response.json()
                
                # Отладка: логируем типы первых 5 элементов
                element_types = [el.get('type') for el in result[:5] if isinstance(el, dict)]
                logger.debug(f"Element types (first 5): {element_types}")
                
                # Форматируем контент
                content = self._format_content(result, output_format)
                
                logger.info(f"Successfully parsed {file_path.name}: {len(content)} chars")
                return content
        
        except httpx.TimeoutException:
            logger.error(f"Timeout while parsing {file_path}")
            return None
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {str(e)}", exc_info=True)
            return None
    
    def _format_content(
        self,
        elements: list,
        output_format: Literal['text', 'markdown']
    ) -> str:
        """
        Форматирует элементы Unstructured в текст
        
        Args:
            elements: Список элементов от Unstructured API
            output_format: Формат вывода
        
        Returns:
            Отформатированный текст
        """
        if output_format == 'markdown':
            # Для markdown сохраняем структуру с заголовками
            content_parts = []
            for element in elements:
                text = element.get('text')
                if not text:  # Пропускаем элементы без текста
                    continue
                
                element_type = element.get('type', 'NarrativeText')
                
                # Обрабатываем официальные типы заголовков
                if element_type == 'Title':
                    content_parts.append(f"\n## {text}\n")
                elif element_type == 'Header':
                    content_parts.append(f"\n### {text}\n")
                elif element_type == 'Table':
                    content_parts.append(f"\n{text}\n")
                else:
                    # Эвристика: короткий текст заглавными буквами = заголовок
                    if len(text) < 100 and text.isupper() and not text.endswith('.'):
                        content_parts.append(f"\n## {text}\n")
                    # Эвристика: короткий текст с первой заглавной = подзаголовок
                    elif (len(text) < 80 and text[0].isupper() and 
                          not text.endswith('.') and '\n' not in text):
                        content_parts.append(f"\n### {text}\n")
                    else:
                        content_parts.append(text)
            
            return '\n'.join(content_parts)
        else:
            # Для обычного текста просто склеиваем
            return '\n\n'.join(
                element.get('text', '') 
                for element in elements 
                if element.get('text')
            )
    
    async def parse_from_bytes(
        self,
        file_content: bytes,
        filename: str,
        output_format: Literal['text', 'markdown'] = 'text'
    ) -> Optional[str]:
        """
        Парсит файл из байтов (для uploaded файлов)
        
        Args:
            file_content: Содержимое файла
            filename: Имя файла
            output_format: Формат вывода
        
        Returns:
            Распарсенный текст или None при ошибке
        """
        logger.info(f"Parsing uploaded file: {filename}, format: {output_format}")
        
        try:
            files = {
                'files': (filename, file_content)
            }
            
            data = {
                'strategy': self.strategy,
                'coordinates': 'false',
                'encoding': 'utf-8',
                'output_encoding': 'utf-8',
                'ocr_languages': 'rus+eng',
                'hi_res_model_name': 'yolox',
                'pdf_infer_table_structure': 'true',
                'skip_infer_table_types': '[]',
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.unstructured_url}/general/v0/general",
                    files=files,
                    data=data
                )
                
                if response.status_code != 200:
                    logger.error(
                        f"Unstructured API error: {response.status_code} - {response.text}"
                    )
                    return None
                
                response.encoding = 'utf-8'
                result = response.json()
                
                content = self._format_content(result, output_format)
                
                logger.info(f"Successfully parsed {filename}: {len(content)} chars")
                return content
        
        except httpx.TimeoutException:
            logger.error(f"Timeout while parsing {filename}")
            return None
        except Exception as e:
            logger.error(f"Error parsing {filename}: {str(e)}", exc_info=True)
            return None


async def parse_document(file_path: Path, output_format: str = 'text') -> Optional[str]:
    """
    Удобная функция для парсинга документа
    
    Args:
        file_path: Путь к файлу
        output_format: Формат вывода ('text' или 'markdown')
    
    Returns:
        Распарсенный текст
    """
    parser = DocumentParser()
    return await parser.parse_file(file_path, output_format)
