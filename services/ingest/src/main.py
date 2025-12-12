"""
Ingest Service - точка входа.

Изолированный сервис обработки документов:
- Парсинг различных форматов (Word, PDF, Excel, PowerPoint, TXT)
- Очистка текста (pipeline клинеров)
- Извлечение метаданных (simple/llm)
- Чанкинг (simple/smart с overlap)
- Эмбеддинг через Ollama и сохранение в pgvector
"""

from threading import Semaphore

from settings import settings
from logging_config import setup_logging, get_logger
from repository import IngestRepository
from worker import Worker

# Компоненты пайплайна
from parsers import build_parser_registry
from cleaners import build_cleaner
from chunkers import build_chunker
from embedders import build_embedder
from metaextractors import build_metaextractor
from pipeline import IngestDocument, ProcessFileEvent


def main():
    """Главная функция сервиса."""
    
    # 1. Настройка логирования
    setup_logging(settings.LOG_LEVEL)
    logger = get_logger("ingest.main")
    
    logger.info("=" * 60)
    logger.info("🚀 Starting Ingest Service")
    logger.info("=" * 60)
    
    # 2. Инициализация репозитория
    logger.info("Initializing repository...")
    repository = IngestRepository(
        database_url=settings.DATABASE_URL,
        files_table="files",
        chunks_table="chunks"
    )
    
    # Сброс зависших processed статусов
    reset_count = repository.reset_processed_to_added()
    if reset_count > 0:
        logger.info(f"🔄 Reset {reset_count} stuck 'processed' files to 'added'")
    
    # 3. Сборка компонентов пайплайна
    logger.info("Building pipeline components...")
    
    parser_registry = build_parser_registry()
    logger.info(f"Parsers: {parser_registry.supported_extensions()}")
    
    cleaner = build_cleaner()
    chunker = build_chunker()
    embedder = build_embedder()
    metaextractor = build_metaextractor()
    
    # Семафоры для ограничения параллелизма
    parse_semaphore = Semaphore(settings.WORKER_MAX_CONCURRENT_PARSING)
    embed_semaphore = Semaphore(settings.WORKER_MAX_CONCURRENT_EMBEDDING)
    llm_semaphore = Semaphore(settings.WORKER_MAX_CONCURRENT_LLM)
    
    # 4. Сборка пайплайна
    logger.info("Assembling pipeline...")
    
    ingest_document = IngestDocument(
        repository=repository,
        parser_registry=parser_registry,
        chunker=chunker,
        embedder=embedder,
        parse_semaphore=parse_semaphore,
        embed_semaphore=embed_semaphore,
        llm_semaphore=llm_semaphore,
        cleaner=cleaner,
        metaextractor=metaextractor,
        temp_dir=settings.TMP_MD_PATH,
    )
    
    process_file_event = ProcessFileEvent(
        ingest_document=ingest_document,
        repository=repository,
    )
    
    # 5. Создание и запуск worker
    logger.info("Creating worker...")
    
    worker = Worker(
        repository=repository,
        filewatcher_api_url=settings.FILEWATCHER_URL,
        process_file_func=process_file_event,
    )
    
    logger.info("=" * 60)
    logger.info("✅ Ingest Service ready")
    logger.info(f"  FileWatcher: {settings.FILEWATCHER_URL}")
    logger.info(f"  Ollama: {settings.OLLAMA_BASE_URL}")
    logger.info(f"  Cleaner pipeline: {settings.CLEANER_PIPELINE}")
    logger.info(f"  Chunker: {settings.CHUNKER_BACKEND} (size={settings.CHUNK_SIZE}, overlap={settings.CHUNK_OVERLAP})")
    logger.info(f"  MetaExtractor pipeline: {settings.METAEXTRACTOR_PIPELINE}")
    logger.info("=" * 60)
    
    # 6. Запуск worker
    worker.start(
        poll_interval=settings.WORKER_POLL_INTERVAL,
        max_workers=settings.WORKER_MAX_CONCURRENT_FILES,
    )


if __name__ == "__main__":
    main()
