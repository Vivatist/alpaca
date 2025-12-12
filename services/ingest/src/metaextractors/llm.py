"""
LLM экстрактор: анализ содержимого через Ollama.

Извлекает:
- title: заголовок документа
- summary: краткое описание
- keywords: ключевые слова (до 5)
- entities: сущности - люди и компании (до 5)
- category: категория документа
- document_date: дата документа (перезаписывает modified_at если найдена)
"""

import os
import json
import re
from typing import Dict, Any, List
import requests

from logging_config import get_logger
from contracts import FileSnapshot
from settings import settings

logger = get_logger("ingest.metaextractor.llm")


# Категории документов
DOCUMENT_CATEGORIES = [
    "Договор подряда",
    "Договор купли-продажи",
    "Трудовой договор",
    "Протокол, меморандум",
    "Доверенность",
    "Акт выполненных работ",
    "Счет-фактура, счет",
    "Техническая документация",
    "Презентация",
    "Письмо",
    "Бухгалтерская документация",
    "Инструкция, регламент",
    "Статья, публикация, книга",
    "Прочее",
]

CATEGORIES_LIST = "\n".join(f"{i+1}. {cat}" for i, cat in enumerate(DOCUMENT_CATEGORIES))


EXTRACTION_PROMPT = """Проанализируй документ и верни JSON с полями:

1. title (строка): заголовок или название документа
2. summary (строка): краткое описание содержимого в 1-2 предложениях
3. keywords (массив строк): до 5 ключевых слов или фраз
4. entities (массив объектов): до 5 важных сущностей. Каждая сущность:
   - type: "person" или "company"
   - name: ФИО человека или название компании
   - role: должность (для person) или роль в документе (для company), может быть null
5. category (строка): СТРОГО одна из категорий:
{categories}
6. document_date (строка или null): дата документа в формате YYYY-MM-DD, если явно указана в тексте (дата договора, протокола, подписания, составления и т.п.). Если дата не найдена — null.

Документ:
{text}

Ответь ТОЛЬКО валидным JSON без пояснений:"""


def llm_extractor(file: FileSnapshot, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    LLM экстрактор: анализ содержимого через Ollama.
    
    Args:
        file: FileSnapshot с заполненным raw_text
        metadata: Накопленные метаданные от предыдущих экстракторов
        
    Returns:
        Dict с обновлёнными метаданными
    """
    result = metadata.copy()
    
    text = file.raw_text or ""
    if not text.strip():
        logger.warning(f"Empty text for LLM extraction | file={file.path}")
        return result
    
    # Берём первые N символов для анализа
    preview_length = settings.LLM_METAEXTRACTOR_PREVIEW_LENGTH
    preview = text[:preview_length]
    
    prompt = EXTRACTION_PROMPT.format(
        categories=CATEGORIES_LIST,
        text=preview
    )

    try:
        response = requests.post(
            f"{settings.OLLAMA_BASE_URL}/api/generate",
            json={
                "model": settings.OLLAMA_LLM_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 800
                }
            },
            timeout=120
        )
        
        if response.status_code != 200:
            logger.warning(f"LLM request failed | status={response.status_code}")
            return result
        
        llm_response = response.json().get('response', '')
        llm_metadata = _parse_llm_response(llm_response)
        
        if llm_metadata:
            result.update(llm_metadata)
            logger.info(f"LLM extraction | category={llm_metadata.get('category', 'N/A')}")
        else:
            logger.warning(f"Failed to parse LLM response")
        
    except Exception as e:
        logger.warning(f"LLM extraction failed | error={e}")
    
    return result


def _parse_llm_response(response: str) -> Dict[str, Any]:
    """Парсинг JSON из ответа LLM."""
    if not response:
        return {}
    
    # Пробуем найти JSON в ответе (может быть вложенным)
    json_match = re.search(r'\{[\s\S]*\}', response)
    if not json_match:
        return {}
    
    try:
        data = json.loads(json_match.group())
        result = {}
        
        # title
        if 'title' in data and isinstance(data['title'], str):
            result['title'] = data['title'].strip()
        
        # summary
        if 'summary' in data and isinstance(data['summary'], str):
            result['summary'] = data['summary'].strip()
        
        # keywords
        if 'keywords' in data and isinstance(data['keywords'], list):
            result['keywords'] = [str(k).strip() for k in data['keywords'][:5] if k]
        
        # entities
        if 'entities' in data and isinstance(data['entities'], list):
            entities = []
            for e in data['entities'][:5]:
                if isinstance(e, dict) and 'name' in e:
                    entity = {
                        'type': e.get('type', 'unknown'),
                        'name': str(e['name']).strip(),
                    }
                    if e.get('role'):
                        entity['role'] = str(e['role']).strip()
                    entities.append(entity)
            if entities:
                result['entities'] = entities
        
        # category - валидация
        if 'category' in data and isinstance(data['category'], str):
            category = data['category'].strip()
            # Проверяем что категория валидна
            if category in DOCUMENT_CATEGORIES:
                result['category'] = category
            else:
                # Пробуем найти похожую категорию
                category_lower = category.lower()
                for valid_cat in DOCUMENT_CATEGORIES:
                    if valid_cat.lower() in category_lower or category_lower in valid_cat.lower():
                        result['category'] = valid_cat
                        break
                else:
                    result['category'] = "Прочее"
        
        # document_date -> modified_at (перезаписывает дату файла если найдена дата документа)
        if 'document_date' in data and data['document_date']:
            date_str = str(data['document_date']).strip()
            parsed_date = _parse_document_date(date_str)
            if parsed_date:
                result['modified_at'] = parsed_date
        
        return result
        
    except json.JSONDecodeError as e:
        logger.debug(f"JSON parse error: {e}")
        return {}


def _parse_document_date(date_str: str) -> str | None:
    """
    Парсинг даты документа в формат ISO 8601.
    
    Поддерживает форматы:
    - YYYY-MM-DD (ISO)
    - DD.MM.YYYY (русский)
    - DD.MM.YY (короткий год)
    - DD/MM/YYYY
    - DD-MM-YYYY
    
    Returns:
        Дата в формате YYYY-MM-DDTHH:MM:SS.ffffff или None
    """
    from datetime import datetime
    
    date_str = date_str.strip()
    
    # Форматы для парсинга (в порядке приоритета)
    formats = [
        "%Y-%m-%d",      # 2023-04-10 (ISO)
        "%d.%m.%Y",      # 10.04.2023 (русский)
        "%d.%m.%y",      # 10.04.23 (короткий год)
        "%d/%m/%Y",      # 10/04/2023
        "%d/%m/%y",      # 10/04/23
        "%d-%m-%Y",      # 10-04-2023
        "%d-%m-%y",      # 10-04-23
        "%Y/%m/%d",      # 2023/04/10
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            # Возвращаем в ISO формате с микросекундами (как в base_extractor)
            return dt.strftime("%Y-%m-%dT00:00:00.000000")
        except ValueError:
            continue
    
    return None
