#!/usr/bin/env python3
"""
PDF Processing Celery Tasks
"""
import sys
import time
from pathlib import Path
from typing import Dict
from datetime import datetime
from tasks.celery import app, setup_logger, config

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, '/app/src')

logger = setup_logger('celery-pdf')

# Импорт Markdown Writer
from parsers.markdown_writer import get_markdown_writer

# Импорт Text Cleaner
from text_cleaner import clean_markdown_text

# Выбор парсера на основе конфига
if config.get('document_processors', {}).get('mock_parsers', {}).get('enabled', False):
    from parsers.mock_parser_module.mock_parser import MockParser
    pdf_parser = MockParser()
    logger.warning("Using MockParser for PDF processing")
else:
    from parsers.pdf_parser_module.pdf_parser import PDFParser
    pdf_parser = PDFParser(enable_ocr=True, ocr_strategy='auto')
    logger.info("Using PDFParser for PDF processing")

# Инициализация Markdown Writer
markdown_writer = get_markdown_writer('/volume_md')



@app.task(bind=True)
def process_pdf_file(self, file_path: str, message: Dict) -> Dict:
    """
    Process PDF file - Celery task
    
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
    file_hash = message.get('hash')  # Хэш от file-watcher
    
    logger.info(f"Processing PDF file | file={file_name} event={event} task_id={self.request.id} hash={file_hash}")
    
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
                'file_type': 'pdf',
                'event': event,
                'error': 'File not found'
            }
        
        # Parse document with PDFParser (передаём file_hash)
        parse_result = pdf_parser.parse(str(path), file_hash=file_hash)
        
        if not parse_result['success']:
            logger.warning(f"PDF parsing failed | file={file_name} error={parse_result.get('error')}")
            return {
                'status': 'error',
                'file_path': message.get('path', ''),
                'file_name': file_name,
                'file_type': 'pdf',
                'event': event,
                'error': parse_result.get('error', 'Parsing failed'),
                'task_id': self.request.id
            }
        
        # Clean markdown content before saving
        markdown_content = parse_result.get('markdown', '')
        if markdown_content:
            cleaned_content = clean_markdown_text(markdown_content)
            parse_result['markdown'] = cleaned_content
        
        # Save to markdown using MarkdownWriter
        timestamp = datetime.utcnow()
        save_result = markdown_writer.save(parse_result, file_name, timestamp)
        
        if not save_result['success']:
            logger.warning(f"Failed to save markdown | file={file_name} error={save_result.get('error')}")
            return {
                'status': 'error',
                'file_path': message.get('path', ''),
                'file_name': file_name,
                'file_type': 'pdf',
                'event': event,
                'error': f"Markdown save failed: {save_result.get('error')}",
                'task_id': self.request.id
            }
        
        processing_time = time.time() - start_time
        processed_timestamp = datetime.utcnow().isoformat() + 'Z'
        
        logger.info(f"PDF processed successfully | file={file_name} output={save_result['markdown_file']} duration={processing_time:.2f}s pages={parse_result['metadata'].get('pages', 0)}")
        
        return {
            'status': 'success',
            'file_path': message.get('path', ''),
            'file_name': file_name,
            'file_type': 'pdf',
            'event': event,
            'processing_time_sec': round(processing_time, 2),
            'processed_timestamp': processed_timestamp,
            
            # Markdown file info from MarkdownWriter
            'markdown_file': save_result['markdown_file'],
            'markdown_path': save_result['markdown_path'],
            'markdown_length': save_result['markdown_length'],
            
            # Metadata
            'metadata': parse_result['metadata'],
            'ocr_enabled': pdf_parser.enable_ocr,
            
            'message': f"PDF document parsed and saved to {save_result['markdown_file']} in {processing_time:.2f}s",
            'task_id': self.request.id
        }
        
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"PDF processing failed | file={file_name} error={type(e).__name__}: {e}")
        
        # Celery will automatically retry
        raise
