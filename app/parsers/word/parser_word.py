import os
import requests
from prefect import task
from pydantic import BaseModel


class FileID(BaseModel):
    """Идентификатор файла (hash + path)"""
    hash: str
    path: str


# Импорты из проекта (будут доступны при запуске из main.py)
from settings import settings
from database import Database
from utils.logging import get_logger

logger = get_logger("alpaca.parser")
db = Database(settings.DATABASE_URL)


@task(name="parser_word_old_task", retries=2, persist_result=True)
def parser_word_old_task(file_id: dict) -> str:
    logger.info(f"🍆 Processing parsing with old parser: {file_id.path}")
    file_id = FileID(**file_id)
    from .word_parser_module.word_parser import WordParser
    try:
        word_parser = WordParser(enable_ocr=True, ocr_strategy='auto')
        parse_result = word_parser.parse(file_id.path)
    except Exception as e:
        logger.error(f"Failed to parse file | file={file_id.path} error={type(e).__name__}: {e}")
        db.mark_as_error(file_id.hash)
        return ""
    logger.info(f"✅ Parsed successfully | file={file_id.path} length={len(parse_result)}")
    return parse_result


@task(name="parser_word_task", retries=2, persist_result=True)
def parser_word_task(file_id: dict) -> str:
    """Task: парсинг документа через Unstructured API"""
    file_id = FileID(**file_id)
    
    try:
        logger.info(f"📖 Processing parsing: {file_id.path}")
        
        # Отправка файла в Unstructured API
        full_path = os.path.join(settings.MONITORED_PATH, file_id.path)
        
        full_path = os.path.join(settings.MONITORED_PATH, file_id.path)
        
        if not os.path.exists(full_path):
            logger.error(f"File not found: {full_path}")
            db.mark_as_error(file_id.hash)
            return ""
        
        with open(full_path, 'rb') as f:
            files = {'files': (file_id.path, f)}
            data = {
                'strategy': 'hi_res',  # hi_res для OCR, auto для обычных документов
                'languages': 'rus,eng',
                'extract_image_block_types': '["Image", "Table"]',
                'coordinates': 'false',
            }
            
            logger.debug(f"Sending to Unstructured API | url={settings.UNSTRUCTURED_API_URL}")
            response = requests.post(
                settings.UNSTRUCTURED_API_URL,
                files=files,
                data=data,
                timeout=300  # 5 минут на парсинг
            )
        
        if response.status_code != 200:
            logger.error(f"Unstructured API error | status={response.status_code} response={response.text[:200]}")
            db.mark_as_error(file_id.hash)
            return ""
        
        # Парсим ответ
        elements = response.json()
        
        if not elements:
            logger.warning(f"No elements returned from Unstructured | file={file_id.path}")
            return ""
        
        # Собираем текст из элементов с сохранением структуры
        markdown_parts = []
        
        for element in elements:
            if 'text' not in element or not element['text'].strip():
                continue
            
            text = element['text'].strip()
            element_type = element.get('type', 'NarrativeText')
            
            # Форматируем по типу элемента
            if element_type == 'Title':
                markdown_parts.append(f"# {text}")
            elif element_type == 'Header':
                markdown_parts.append(f"## {text}")
            elif element_type == 'ListItem':
                markdown_parts.append(f"- {text}")
            elif element_type == 'Table':
                markdown_parts.append(f"\n{text}\n")
            elif element_type in ['NarrativeText', 'UncategorizedText', 'Text']:
                markdown_parts.append(text)
            elif element_type == 'Address':
                markdown_parts.append(f"**{text}**")
            elif element_type == 'EmailAddress':
                markdown_parts.append(f"`{text}`")
            else:
                # Неизвестный тип - просто текст
                markdown_parts.append(text)
        
        parsed_text = '\n\n'.join(markdown_parts)
        
        logger.info(f"✅ Parsed successfully | file={file_id.path} elements={len(elements)} length={len(parsed_text)}")
        
        return parsed_text
        
    except requests.exceptions.Timeout:
        logger.error(f"Unstructured API timeout | file={file_id.path}")
        db.mark_as_error(file_id.hash)
        return ""
    except Exception as e:
        logger.error(f"Failed to parse file | file={file_id.path} error={type(e).__name__}: {e}")
        db.mark_as_error(file_id.hash)
        return ""


