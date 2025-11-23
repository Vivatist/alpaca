"""
ALPACA RAG - Единая точка входа
"""
import os
import warnings

# Отключаем UserWarning ДО любых импортов
os.environ.setdefault("PYTHONWARNINGS", "ignore::UserWarning")
warnings.filterwarnings("ignore", category=UserWarning)

import requests
import psycopg2
import psycopg2.extras
from time import sleep
from typing import Dict, List, Tuple

from app.parsers.word.parser_word import parser_word_task, parser_word_old_task

# Отключаем логирование Prefect ДО импорта
os.environ["PREFECT_LOGGING_LEVEL"] = "WARNING"
os.environ["PREFECT_LOGGING_TO_API_ENABLED"] = "false"

from datetime import timedelta
from prefect import flow, serve, task
from pydantic import BaseModel


class FileID(BaseModel):
    """Идентификатор файла (hash + path)"""
    hash: str
    path: str
        
        
from utils.logging import setup_logging, get_logger
from utils.process_lock import ProcessLock
from app.file_watcher import FileWatcherService
from settings import settings
from database import Database

# Настраиваем логирование в каждом процессе
setup_logging()
logger = get_logger("alpaca.main")

# Сервисы
file_watcher = FileWatcherService(
    database_url=settings.DATABASE_URL,
    monitored_path=settings.MONITORED_PATH,
    allowed_extensions=settings.ALLOWED_EXTENSIONS.split(','),
    file_min_size=settings.FILE_MIN_SIZE,
    file_max_size=settings.FILE_MAX_SIZE,
    excluded_dirs=settings.EXCLUDED_DIRS.split(','),
    excluded_patterns=settings.EXCLUDED_PATTERNS.split(',')
)

db = Database(settings.DATABASE_URL)


@flow(name="file_watcher_flow")
def file_watcher_flow():
    """Сканирование и синхронизация файлов"""
    result = file_watcher.scan_and_sync()
    
    return result


@task(name="process_deleted_file", retries=2, persist_result=True)
def task_process_deleted_file(
    db: Database, file_id: FileID) -> FileID:
    """Task: обработка deleted файла"""
    try:
        chunks_deleted = db.delete_chunks_by_hash(file_id.hash)
        db.delete_file_by_hash(file_id.hash)
        logger.info(f"Deleted {file_id.path} and {chunks_deleted} chunks")
    except Exception as e:
        logger.error(f"ERROR when trying to delete a file {file_id.path}: {e}")
        return None
    return file_id


@task(name="chunking", retries=2)
def task_chunking(file_id: dict, text: str) -> List[str]:
    """Task: разбивка текста на чанки
    
    Args:
        file_id: dict с hash и path
        text: распарсенный текст документа
        
    Returns:
        List[str]: список чанков
    """
    file_id = FileID(**file_id)
    
    try:
        logger.info(f"🔪 Chunking: {file_id.path}")
        
        # Разбиваем текст на чанки (простая стратегия - по параграфам с максимальным размером)
        chunks = []
        max_chunk_size = 1000  # символов
        paragraphs = text.split('\n\n')
        
        current_chunk = ""
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # Если добавление параграфа превысит лимит - сохраняем текущий чанк
            if len(current_chunk) + len(para) > max_chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = para
            else:
                current_chunk += "\n\n" + para if current_chunk else para
        
        # Добавляем последний чанк
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        if not chunks:
            logger.warning(f"No chunks created for {file_id.path}")
            return []
        
        logger.info(f"✅ Created {len(chunks)} chunks for {file_id.path}")
        
        return chunks
        
    except Exception as e:
        logger.error(f"Failed to chunk text | file={file_id.path} error={type(e).__name__}: {e}")
        return []


@task(name="embedding", retries=2)
def task_embedding(file_id: dict, chunks: List[str]) -> int:
    """Task: создание эмбеддингов через Ollama и сохранение в БД
    
    Args:
        file_id: dict с hash и path
        chunks: список текстовых чанков
        
    Returns:
        int: количество успешно сохранённых чанков
    """
    file_id = FileID(**file_id)
    
    try:
        if not chunks:
            logger.warning(f"No chunks to embed for {file_id.path}")
            return 0
        
        logger.info(f"🔮 Embedding {len(chunks)} chunks: {file_id.path}")
        
        # Создаём эмбеддинги через Ollama
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                inserted_count = 0
                
                for idx, chunk_text in enumerate(chunks):
                    # Получаем эмбеддинг от Ollama
                    try:
                        response = requests.post(
                            f"{settings.OLLAMA_BASE_URL}/api/embeddings",
                            json={
                                "model": settings.OLLAMA_EMBEDDING_MODEL,
                                "prompt": chunk_text
                            },
                            timeout=60
                        )
                        
                        if response.status_code != 200:
                            logger.error(f"Ollama embedding error | status={response.status_code}")
                            continue
                        
                        embedding = response.json().get('embedding')
                        
                        if not embedding:
                            logger.error(f"No embedding in response for chunk {idx}")
                            continue
                        
                        # Конвертируем в PostgreSQL vector формат
                        embedding_str = '[' + ','.join(map(str, embedding)) + ']'
                        
                        # Метаданные чанка
                        metadata = {
                            'file_hash': file_id.hash,
                            'file_path': file_id.path,
                            'chunk_index': idx,
                            'total_chunks': len(chunks)
                        }
                        
                        # Вставляем в БД
                        cur.execute("""
                            INSERT INTO chunks (content, metadata, embedding)
                            VALUES (%s, %s, %s::vector)
                        """, (chunk_text, psycopg2.extras.Json(metadata), embedding_str))
                        
                        inserted_count += 1
                        
                    except Exception as e:
                        logger.error(f"Error embedding chunk {idx}: {e}")
                        continue
                
                conn.commit()
        
        logger.info(f"✅ Embedded {inserted_count}/{len(chunks)} chunks for {file_id.path}")
        
        return inserted_count
        
    except Exception as e:
        logger.error(f"Failed to embed chunks | file={file_id.path} error={type(e).__name__}: {e}")
        return 0




@flow(name="ingest_pipeline")
def ingest_pipeline(file_id: dict) -> str:
    """Входная точка пайплайна нового документа"""
    file_id = FileID(**file_id)
    logger.info(f"🍎 Start ingest pipeline: {file_id.path} (hash: {file_id.hash[:8]}...)")
    db.mark_as_processed(file_id.hash)
    
    # 1. Парсим файл в сырой текст
    if file_id.path.lower().endswith('.docx'):  
        raw_text = parser_word_old_task(file_id.model_dump())
    else:
        logger.error(f"Unsupported file type: {file_id.path}")
        db.mark_as_error(file_id.hash)
        return ""

    if not raw_text or not raw_text.strip():
        logger.error(f"Empty parsed text for {file_id.path}")
        db.mark_as_error(file_id.hash)
        return ""
    
    # 2. Сохраняем распарсенный текст в temp_parsed
    temp_dir = os.path.join(os.path.dirname(__file__), "temp_parsed")
    temp_file_path = os.path.join(temp_dir, f"{file_id.path}.md")
    
    os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)
    
    with open(temp_file_path, "w", encoding="utf-8") as f:
        f.write(raw_text)
    
    # 3. Чанкинг
    chunks = task_chunking(file_id.model_dump(), raw_text)
    
    if not chunks:
        logger.warning(f"No chunks created for {file_id.path}")
        db.mark_as_error(file_id.hash)
        return ""
    
    # 4. Эмбеддинг
    chunks_count = task_embedding(file_id.model_dump(), chunks)
    
    if chunks_count == 0:
        logger.warning(f"No embeddings created for {file_id.path}")
        db.mark_as_error(file_id.hash)
        return ""
    
    db.mark_as_ok(file_id.hash)
    logger.info(f"✅ File processed successfully: {file_id.path} | chunks={chunks_count}")
    return ""


@flow(name="process_pending_files_flow")
def process_pending_files_flow():
    """Обработка изменений статусов файлов (added/updated → ingestion, deleted → cleanup)"""
    pending_files = db.get_pending_files()
    total_pending = sum(len(files) for files in pending_files.values())
    logger.info(f"📋 Found {total_pending} pending files (deleted:{len(pending_files['deleted'])}, updated:{len(pending_files['updated'])}, added:{len(pending_files['added'])})")

    # Цикл обработки файлов до тех пор, пока есть отмеченные как deleted pending-файлы
    for file_id in pending_files['deleted']:
        task_process_deleted_file(db, file_id)

    # Цикл обработки файлов до тех пор, пока есть отмеченные как updated pending-файлы
    for file_id in pending_files['updated']:
        task_process_deleted_file(db, file_id)
        ingest_pipeline(file_id.model_dump())

    # Цикл обработки файлов до тех пор, пока есть отмеченные как added pending-файлы
    for file_id in pending_files['added']:
        ingest_pipeline(file_id.model_dump())

    return
        
        
if __name__ == "__main__":
    # Защита от дублирования процессов (как HTTP сервер проверяет порт)
    process_lock = ProcessLock('/tmp/alpaca_rag.pid')
    process_lock.acquire()
    # process_lock.setup_handlers()  # Отключено: конфликт с Prefect Runner SIGTERM
    
    try:
        logger.info("Starting ALPACA RAG system...")
        
        # Сброс статусов processed у файлов в базе при старте
        reset_count = file_watcher.reset_processed_statuses()
            
        # Запуск нескольких flows с ограничением параллелизма
        serve(
            file_watcher_flow.to_deployment(
                name="file-watcher",
                interval=timedelta(seconds=settings.SCAN_MONITORED_FOLDER_INTERVAL),
                description="Сканирование и синхронизация файлов",
                concurrency_limit=1
            ),
            process_pending_files_flow.to_deployment(
                name="process_pending_files_flow",
                interval=timedelta(seconds=settings.PROCESS_FILE_CHANGES_INTERVAL),
                description="Обработка изменений статусов файлов",
                concurrency_limit=1 # settings.MAX_HEAVY_WORKFLOWS
            )
        )
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
    finally:
        process_lock.release()
