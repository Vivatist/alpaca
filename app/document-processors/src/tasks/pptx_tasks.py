#!/usr/bin/env python3
"""
PowerPoint Processing Celery Tasks
"""
import sys
import time
from pathlib import Path
from typing import Dict
from datetime import datetime
from tasks.celery import app, setup_logger, config

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, '/app/src')

logger = setup_logger('celery-pptx')

# Импорт Markdown Writer
from parsers.markdown_writer import get_markdown_writer

# Импорт Text Cleaner
from text_cleaner import clean_markdown_text

# Выбор парсера на основе конфига
if config.get('document_processors', {}).get('mock_parsers', {}).get('enabled', False):
    from parsers.mock_parser_module.mock_parser import MockParser
    pptx_parser = MockParser()
    logger.warning("Using MockParser for PowerPoint processing")
else:
    from parsers.pptx_parser_module.pptx_parser import PptxParser
    pptx_parser = PptxParser()
    logger.info("Using PptxParser for PowerPoint processing")

# Инициализация Markdown Writer
markdown_writer = get_markdown_writer('/volume_md')


@app.task(bind=True)
def process_pptx_file(self, file_path: str, message: Dict) -> Dict:
    """Process PowerPoint (PPTX) file with PptxParser - Celery task"""
    file_name = message.get('name', Path(file_path).name)
    event = message.get('event', 'unknown')
    file_hash = message.get('hash')  # Хэш от file-watcher
    
    logger.info(f"Processing PowerPoint file | file={file_name} event={event} task_id={self.request.id} hash={file_hash}")
    
    start_time = time.time()
    
    try:
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"File not found | file={file_name} path={file_path}")
            return {
                'status': 'error',
                'file_path': message.get('path', ''),
                'file_name': file_name,
                'file_type': 'pptx',
                'event': event,
                'error': 'File not found',
                'task_id': self.request.id
            }
        
        # Parse presentation with PptxParser (передаём file_hash)
        parse_result = pptx_parser.parse(str(path), file_hash=file_hash)
        
        if not parse_result['success']:
            logger.warning(f"PowerPoint parsing failed | file={file_name} error={parse_result.get('error')}")
            return {
                'status': 'error',
                'file_path': message.get('path', ''),
                'file_name': file_name,
                'file_type': 'pptx',
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
                'file_type': 'pptx',
                'event': event,
                'error': f"Markdown save failed: {save_result.get('error')}",
                'task_id': self.request.id
            }
        
        processing_time = time.time() - start_time
        processed_timestamp = datetime.utcnow().isoformat() + 'Z'
        
        logger.info(f"PowerPoint processed successfully | file={file_name} output={save_result['markdown_file']} slides={parse_result['metadata'].get('slides', 0)} duration={processing_time:.2f}s")
        
        return {
            'status': 'success',
            'file_path': message.get('path', ''),
            'file_name': file_name,
            'file_type': 'pptx',
            'event': event,
            'processing_time_sec': round(processing_time, 2),
            'processed_timestamp': processed_timestamp,
            
            # Markdown file info from MarkdownWriter
            'markdown_file': save_result['markdown_file'],
            'markdown_path': save_result['markdown_path'],
            'markdown_length': save_result['markdown_length'],
            
            # Metadata
            'metadata': parse_result['metadata'],
            'slides_count': parse_result['metadata'].get('slides', 0),
            'author': parse_result['metadata'].get('author', ''),
            
            'message': f"PowerPoint presentation parsed and saved to {save_result['markdown_file']} in {processing_time:.2f}s",
            'task_id': self.request.id
        }
        
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"PowerPoint processing failed | file={file_name} error={type(e).__name__}: {e}")
        raise
