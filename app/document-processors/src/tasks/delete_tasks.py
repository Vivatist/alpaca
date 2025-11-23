#!/usr/bin/env python3
"""
Document Deletion Proxy Task

Прокси-задача для удаления документов из векторной БД.
Делегирует фактическое удаление vector-worker через HTTP API.

Принцип единой ответственности:
- document-processors: обработка и парсинг документов
- vector-worker: управление векторной БД (добавление + удаление)
- delete_tasks: прокси между file-watcher и vector-worker
"""
import os
import requests
from pathlib import Path
from typing import Dict
from tasks.celery import app, setup_logger

logger = setup_logger('celery-file-deletion')

# Vector Worker API endpoint
VECTOR_WORKER_URL = os.getenv('VECTOR_WORKER_URL', 'http://vector-worker:8000')


@app.task(bind=True)
def process_file_deletion(self, file_data: Dict) -> Dict:
    """
    Proxy task для удаления файла из векторной БД
    
    Делегирует удаление vector-worker API, который:
    1. Ищет документ в Dify по file_hash
    2. Удаляет из Dify Dataset
    3. Удаляет связанный MD файл
    
    Args:
        file_data: Данные удаленного файла
            - path: Путь к файлу
            - name: Имя файла
            - extension: Расширение
            - hash: Хэш файла (для поиска в Dify)
            - event: 'deleted'
    
    Returns:
        Dict с результатом удаления
    """
    file_path = file_data.get('path', '')
    file_name = file_data.get('name', '')
    file_hash = file_data.get('hash', '')
    file_type = file_data.get('extension', 'unknown').lstrip('.')
    
    logger.info(f"Processing file deletion | file={file_name} type={file_type} hash={file_hash} task_id={self.request.id}")
    
    if not file_hash:
        logger.error(f"No file hash provided | file={file_name}")
        return {
            'status': 'error',
            'file_name': file_name,
            'error': 'Missing file hash',
            'task_id': self.request.id
        }
    
    try:
        # Отправка DELETE запроса к vector-worker API
        url = f"{VECTOR_WORKER_URL}/documents/{file_hash}"
        params = {'type': 'file_hash'}
        
        logger.info(f"Sending deletion request to vector-worker | url={url} hash={file_hash}")
        
        response = requests.delete(url, params=params, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Document deleted successfully | file={file_name} status={result.get('status')}")
            
            return {
                'status': 'deleted',
                'file_path': file_path,
                'file_name': file_name,
                'file_type': file_type,
                'file_hash': file_hash,
                'event': 'deleted',
                'message': f'Document deleted from vector DB: {file_name}',
                'task_id': self.request.id,
                'vector_worker_response': result
            }
        
        elif response.status_code == 404:
            result = response.json()
            logger.warning(f"Document not found in vector DB | file={file_name} hash={file_hash}")
            
            return {
                'status': 'not_found',
                'file_path': file_path,
                'file_name': file_name,
                'file_hash': file_hash,
                'message': f'Document not found in vector DB: {file_name}',
                'task_id': self.request.id,
                'vector_worker_response': result
            }
        
        else:
            logger.error(f"Vector worker returned error | file={file_name} status={response.status_code} response={response.text[:200]}")
            
            return {
                'status': 'error',
                'file_name': file_name,
                'file_hash': file_hash,
                'error': f'Vector worker error: HTTP {response.status_code}',
                'task_id': self.request.id
            }
    
    except requests.exceptions.Timeout:
        logger.error(f"Vector worker timeout | file={file_name}")
        return {
            'status': 'timeout',
            'file_name': file_name,
            'error': 'Vector worker timeout',
            'task_id': self.request.id
        }
    
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Cannot connect to vector worker | file={file_name} error={e}")
        return {
            'status': 'connection_error',
            'file_name': file_name,
            'error': f'Cannot connect to vector worker: {VECTOR_WORKER_URL}',
            'task_id': self.request.id
        }
    
    except Exception as e:
        logger.error(f"Deletion failed | file={file_name} error={type(e).__name__}: {e}")
        raise
