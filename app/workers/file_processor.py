"""
Обработка документов через Prefect flows
Замена N8N workflow на Python код с Prefect оркестрацией
"""

from pathlib import Path
from typing import Optional
import logging

from prefect import flow, task
from prefect.tasks import task_input_hash
from datetime import timedelta

from settings import settings
from app.core.parser import parse_document
from app.core.chunker import chunk_text
from app.core.embedder import generate_embeddings
from app.db.connection import get_db

logger = logging.getLogger(__name__)


@task(
    name="Parse Document",
    description="Парсит документ через Unstructured API",
    cache_key_fn=task_input_hash,
    cache_expiration=timedelta(hours=24),
    retries=2,
    retry_delay_seconds=30
)
async def parse_document_task(file_path: str, file_hash: str) -> Optional[str]:
    """
    Парсит документ
    
    Args:
        file_path: Относительный путь к файлу
        file_hash: SHA256 хэш файла
    
    Returns:
        Распарсенный текст или None
    """
    logger.info(f"Parsing: {file_path}")
    
    full_path = settings.MONITORED_PATH / file_path
    parsed_text = await parse_document(full_path, output_format='text')
    
    if not parsed_text or len(parsed_text) < 100:
        logger.error(f"Parsed text too short or empty: {file_path}")
        return None
    
    logger.info(f"Parsed {len(parsed_text)} chars from {file_path}")
    return parsed_text


@task(
    name="Chunk Text",
    description="Разбивает текст на чанки",
    retries=1
)
def chunk_text_task(text: str) -> list[str]:
    """
    Разбивает текст на чанки
    
    Args:
        text: Исходный текст
    
    Returns:
        Список чанков
    """
    chunks = chunk_text(
        text,
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP
    )
    
    logger.info(f"Created {len(chunks)} chunks")
    return chunks


@task(
    name="Generate Embeddings",
    description="Генерирует векторные представления через Ollama",
    retries=2,
    retry_delay_seconds=60
)
async def generate_embeddings_task(chunks: list[str]) -> list[list[float]]:
    """
    Генерирует embeddings для чанков
    
    Args:
        chunks: Список текстовых чанков
    
    Returns:
        Список векторов embeddings
    """
    embeddings = await generate_embeddings(
        chunks,
        batch_size=settings.PROCESSING_BATCH_SIZE
    )
    
    logger.info(f"Generated {len(embeddings)} embeddings")
    return embeddings


@task(
    name="Save to Database",
    description="Сохраняет чанки и embeddings в БД",
    retries=2
)
async def save_to_database_task(
    file_hash: str,
    file_path: str,
    chunks: list[str],
    embeddings: list[list[float]]
) -> bool:
    """
    Сохраняет чанки в documents таблицу
    
    Args:
        file_hash: SHA256 хэш файла
        file_path: Путь к файлу
        chunks: Список чанков
        embeddings: Список embeddings
    
    Returns:
        True если успешно
    """
    if len(chunks) != len(embeddings):
        logger.error(f"Mismatch: {len(chunks)} chunks vs {len(embeddings)} embeddings")
        return False
    
    async with get_db() as db:
        # Удаляем старые чанки если есть
        await db.execute(
            "DELETE FROM documents WHERE file_hash = $1",
            file_hash
        )
        
        # Вставляем новые чанки
        for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            await db.execute("""
                INSERT INTO documents 
                (file_hash, file_path, chunk_index, chunk_text, embedding)
                VALUES ($1, $2, $3, $4, $5)
            """, file_hash, file_path, idx, chunk, embedding)
        
        logger.info(f"Saved {len(chunks)} chunks to database")
        return True


@task(
    name="Update File Status",
    description="Обновляет статус файла в file_state",
    retries=2
)
async def update_file_status_task(file_hash: str, status: str) -> bool:
    """
    Обновляет status_sync в file_state
    
    Args:
        file_hash: SHA256 хэш файла
        status: Новый статус ('ok', 'error', etc.)
    
    Returns:
        True если успешно
    """
    async with get_db() as db:
        await db.execute("""
            UPDATE file_state 
            SET status_sync = $1, last_checked = NOW()
            WHERE file_hash = $2
        """, status, file_hash)
    
    logger.info(f"Updated status to '{status}' for hash {file_hash[:8]}...")
    return True


@flow(
    name="Process Document",
    description="Полный цикл обработки документа: parse → chunk → embed → save",
    retries=1,
    retry_delay_seconds=120
)
async def process_document_flow(file_path: str, file_hash: str) -> bool:
    """
    Полный цикл обработки документа (замена N8N workflow)
    
    Шаги:
    1. Парсинг через Unstructured API
    2. Чанкирование текста
    3. Генерация эмбеддингов через Ollama
    4. Сохранение в БД
    5. Обновление статуса
    
    Args:
        file_path: Относительный путь к файлу
        file_hash: SHA256 хэш файла
    
    Returns:
        True если успешно, False если ошибка
    """
    logger.info(f"🚀 Processing: {file_path} (hash: {file_hash[:8]}...)")
    
    try:
        # 1. Парсинг документа
        parsed_text = await parse_document_task(file_path, file_hash)
        
        if not parsed_text:
            await update_file_status_task(file_hash, 'error')
            return False
        
        # 2. Чанкирование
        chunks = chunk_text_task(parsed_text)
        
        if not chunks:
            await update_file_status_task(file_hash, 'error')
            return False
        
        # 3. Генерация embeddings
        embeddings = await generate_embeddings_task(chunks)
        
        if not embeddings or len(embeddings) != len(chunks):
            await update_file_status_task(file_hash, 'error')
            return False
        
        # 4. Сохранение в БД
        success = await save_to_database_task(file_hash, file_path, chunks, embeddings)
        
        if not success:
            await update_file_status_task(file_hash, 'error')
            return False
        
        # 5. Обновляем статус на 'ok'
        await update_file_status_task(file_hash, 'ok')
        
        logger.info(f"✅ Successfully processed {file_path}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to process {file_path}: {e}", exc_info=True)
        
        # Помечаем как error
        try:
            await update_file_status_task(file_hash, 'error')
        except Exception as db_error:
            logger.error(f"Failed to update error status: {db_error}")
        
        return False


@flow(
    name="Process Queue",
    description="Обработка очереди файлов из file_state",
    log_prints=True
)
async def process_queue_flow() -> dict:
    """
    Обработка очереди файлов (замена main-loop)
    
    Логика:
    - Берём файлы со статусом 'added' или 'updated'
    - Обрабатываем не больше MAX_CONCURRENT_PROCESSING одновременно
    - Пропускаем если уже есть 'processed' файлы
    
    Returns:
        Статистика обработки
    """
    async with get_db() as db:
        # Проверяем текущее количество обрабатываемых
        current_processing = await db.fetchval("""
            SELECT COUNT(*) FROM file_state 
            WHERE status_sync = 'processed'
        """)
        
        current_processing = current_processing or 0
        slots_available = settings.MAX_CONCURRENT_PROCESSING - current_processing
        
        if slots_available <= 0:
            logger.debug("No available slots for processing")
            return {'processed': 0, 'skipped': 0}
        
        # Получаем файлы для обработки
        files = await db.fetch("""
            SELECT file_path, file_hash, file_size
            FROM file_state
            WHERE status_sync IN ('added', 'updated')
            ORDER BY last_checked ASC
            LIMIT $1
        """, slots_available)
        
        if not files:
            logger.debug("No files to process")
            return {'processed': 0, 'skipped': 0}
        
        logger.info(f"📋 Processing {len(files)} files")
        
        # Помечаем как 'processed'
        for file in files:
            await db.execute("""
                UPDATE file_state 
                SET status_sync = 'processed'
                WHERE file_hash = $1
            """, file['file_hash'])
        
        # Обрабатываем файлы через Prefect subflows
        results = []
        for file in files:
            result = await process_document_flow(
                file['file_path'],
                file['file_hash']
            )
            results.append(result)
        
        success_count = sum(1 for r in results if r)
        failed_count = len(results) - success_count
        
        logger.info(
            f"📊 Queue processed: {success_count} success, {failed_count} failed"
        )
        
        return {
            'processed': success_count,
            'failed': failed_count,
            'total': len(results)
        }
