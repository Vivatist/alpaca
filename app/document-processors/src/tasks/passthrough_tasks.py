#!/usr/bin/env python3
"""
Passthrough Processing Celery Tasks

Задачи для копирования файлов в /volume_md БЕЗ обработки и парсинга.
Используется для форматов, которые Dify умеет обрабатывать напрямую (изображения, JSON, etc).
"""
import sys
import os
import shutil
import time
from pathlib import Path
from typing import Dict
from datetime import datetime
from tasks.celery import app, setup_logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, '/app/src')

logger = setup_logger('celery-passthrough')


@app.task(bind=True)
def send_without_processing(self, file_path: str, message: Dict) -> Dict:
    """
    Copy file to /volume_md without processing - Celery task
    
    Копирует файл в директорию /volume_md с оригинальным расширением,
    без конвертации в Markdown. Vector-worker обработает его через Dify API.
    
    Celery automatically:
    - Manages connection to RabbitMQ (no manual reconnect)
    - Handles retries on failure
    - Manages worker threads (no manual threading)
    - ACKs message after successful completion
    
    Args:
        file_path: Full path to file
        message: Original message from file-watcher (includes 'hash' field)
        
    Returns:
        Dict: Processing result
    """
    file_name = message.get('name', Path(file_path).name)
    event = message.get('event', 'unknown')
    file_hash = message.get('hash')
    
    logger.info(f"Processing file without conversion | file={file_name} event={event} task_id={self.request.id} hash={file_hash}")
    
    start_time = time.time()
    
    try:
        # Check file exists
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"File not found | file={file_name}")
            return {
                'status': 'error',
                'file_path': message.get('path', ''),
                'file_name': file_name,
                'file_type': path.suffix.lstrip('.'),
                'event': event,
                'error': 'File not found',
                'task_id': self.request.id
            }
        
        # Prepare output path with original extension
        output_dir = Path('/volume_md')
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Use original filename (with extension)
        output_file = output_dir / file_name
        
        # If file exists, add timestamp to avoid overwriting
        if output_file.exists():
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            stem = output_file.stem
            suffix = output_file.suffix
            output_file = output_dir / f"{stem}_{timestamp}{suffix}"
            logger.debug(f"File exists, using timestamped name | new_name={output_file.name}")
        
        # Copy file to volume_md
        shutil.copy2(file_path, str(output_file))
        
        # Создать файл с метаданными для vector-worker (чтобы знал file_hash для удаления)
        metadata_file = output_dir / f"{output_file.name}.metadata.json"
        import json
        metadata = {
            'file_hash': file_hash,
            'file_name': file_name,
            'file_path': message.get('path', ''),
            'file_size': output_file.stat().st_size,
            'processed_at': datetime.utcnow().isoformat() + 'Z'
        }
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        file_size = output_file.stat().st_size
        processing_time = time.time() - start_time
        processed_timestamp = datetime.utcnow().isoformat() + 'Z'
        
        logger.info(f"File copied successfully | file={file_name} output={output_file.name} size={file_size} duration={processing_time:.2f}s metadata={metadata_file.name}")
        
        return {
            'status': 'success',
            'file_path': message.get('path', ''),
            'file_name': file_name,
            'file_type': path.suffix.lstrip('.'),
            'event': event,
            'output_file': str(output_file),
            'output_name': output_file.name,
            'file_size': file_size,
            'file_hash': file_hash,
            'processing_time': round(processing_time, 2),
            'processed_at': processed_timestamp,
            'task_id': self.request.id
        }
    
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"Processing failed | file={file_name} error={type(e).__name__}: {e} duration={processing_time:.2f}s")
        
        return {
            'status': 'error',
            'file_path': message.get('path', ''),
            'file_name': file_name,
            'file_type': Path(file_path).suffix.lstrip('.'),
            'event': event,
            'error': f"{type(e).__name__}: {str(e)}",
            'processing_time': round(processing_time, 2),
            'task_id': self.request.id
        }
