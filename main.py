"""Основной модуль worker с совместимостью старого API."""

import os
from typing import Dict, Any
from threading import Semaphore

from utils.logging import setup_logging, get_logger
from utils.worker import Worker
from settings import settings
from core.infrastructure.database.postgres import PostgresFileRepository
from core.application.files import FileService
from core.domain.files.models import FileSnapshot
from tests.runner import run_tests_on_startup
from core.application.files import ResetStuckFiles
from core.application.processing import IngestDocument, ProcessFileEvent
from core.domain.document_processing import (
    get_parser_for_path,
    embed_chunks,
    chunk_document,
)
from core.application.document_processing.parsers import WordParser

logger = get_logger("core.worker")

DOC_EXTENSIONS = (".doc", ".docx")
word_parser = WordParser(enable_ocr=True)


def legacy_parser_resolver(file_path: str):
    """Возвращаем общий парсер, но doc/docx мапим на экспонированный word_parser."""
    lower = file_path.lower()
    if lower.endswith(DOC_EXTENSIONS):
        return word_parser
    return get_parser_for_path(file_path)

# Инициализация
db = PostgresFileRepository(settings.DATABASE_URL)
file_service = FileService(db)
FILEWATCHER_API = os.getenv("FILEWATCHER_API_URL", "http://localhost:8081")

# Семафоры для ограничения конкурентности разных операций (из settings)
PARSE_SEMAPHORE = Semaphore(settings.WORKER_MAX_CONCURRENT_PARSING)
EMBED_SEMAPHORE = Semaphore(settings.WORKER_MAX_CONCURRENT_EMBEDDING)
LLM_SEMAPHORE = Semaphore(settings.WORKER_MAX_CONCURRENT_LLM)

ingest_document = IngestDocument(
    file_service=file_service,
    database=db,
    parser_resolver=legacy_parser_resolver,
    chunker=chunk_document,
    embedder=embed_chunks,
    parse_semaphore=PARSE_SEMAPHORE,
    embed_semaphore=EMBED_SEMAPHORE,
)

process_file_use_case = ProcessFileEvent(
    ingest_document=ingest_document,
    file_service=file_service,
)

# Backward-compatible attribute for legacy tests/imports
chunking = chunk_document


def ingest_pipeline(file: FileSnapshot) -> bool:
    """Backward-compatible entry point для тестов и скриптов."""
    return ingest_document(file)


def process_file(file_info: Dict[str, Any]) -> bool:
    """Backward-compatible entry point для тестов (имитирует старую логику)."""
    file = FileSnapshot(**file_info)
    logger.info(f"Processing file (compat layer): {file.path} status={file.status_sync}")

    try:
        if file.status_sync == "deleted":
            file_service.delete_file_and_chunks(file)
            return True
        if file.status_sync == "updated":
            file_service.delete_chunks_only(file)
            return ingest_pipeline(file)
        if file.status_sync == "added":
            return ingest_pipeline(file)

        logger.warning(f"Unknown status in compat layer: {file.status_sync}")
        return False
    except Exception as exc:
        logger.error(f"✗ Compat process_file failed | file={file.path} error={exc}")
        file_service.mark_as_error(file)
        return False

if __name__ == "__main__":
    # Запуск тестов при старте (если включено в настройках)
    tests_passed = run_tests_on_startup(settings)

    if not tests_passed:
        exit(1)

    # Переинициализируем logging после тестов (pytest может закрыть handlers)
    setup_logging()
    logger.info("🚀 Запуск worker после успешного прохождения тестов")

    # Сбрасываем зависшие 'processed' статусы на 'added' при старте
    try:
        reset_use_case = ResetStuckFiles(db)
        reset_count = reset_use_case()
        if reset_count > 0:
            logger.info(f"🔄 Reset {reset_count} stuck 'processed' files to 'added' on startup")
    except Exception as e:
        logger.error(f"Failed to reset processed statuses: {e}")

    # Создаём worker и запускаем
    worker = Worker(
        db=db,
        filewatcher_api_url=FILEWATCHER_API,
        process_file_func=process_file_use_case,
    )
    worker.start(poll_interval=settings.WORKER_POLL_INTERVAL, max_workers=settings.WORKER_MAX_CONCURRENT_FILES)

