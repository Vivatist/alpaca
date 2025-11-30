from __future__ import annotations

import os
from dataclasses import dataclass
from threading import Semaphore

from settings import Settings, settings
from core.application.document_processing.parsers import (
    WordParser,
    PDFParser,
    PowerPointParser,
    ExcelParser,
    TXTParser,
)
from core.application.document_processing.chunking import chunk_document as default_chunker
from core.application.document_processing.embedding import custom_embedding, langchain_embedding
from core.application.processing import IngestDocument, ProcessFileEvent
from core.domain.document_processing import ParserRegistry
from core.infrastructure.database.postgres import PostgresFileRepository
from utils.worker import Worker


@dataclass
class WorkerApplication:
    """Контейнер готового worker'а."""
    
    worker: Worker
    repository: PostgresFileRepository


def build_worker_application(app_settings: Settings = settings) -> WorkerApplication:
    """Собирает и возвращает готовый worker."""
    
    # 1. Repository
    repository = PostgresFileRepository(
        database_url=app_settings.DATABASE_URL,
        files_table="files",
    )
    
    # 2. Parsers
    word_parser = WordParser(enable_ocr=True)
    parsers = ParserRegistry({
        (".doc", ".docx"): word_parser,
        (".pdf",): PDFParser(),
        (".pptx", ".ppt"): PowerPointParser(),
        (".xlsx", ".xls"): ExcelParser(),
        (".txt",): TXTParser(),
    })
    
    # 3. Chunker
    chunker = default_chunker
    
    # 4. Embedder
    if app_settings.EMBEDDER_BACKEND == "langchain":
        embedder = langchain_embedding
    else:
        embedder = custom_embedding
    
    # 5. Ingest pipeline
    ingest = IngestDocument(
        repository=repository,
        parser_registry=parsers,
        chunker=chunker,
        embedder=embedder,
        parse_semaphore=Semaphore(app_settings.WORKER_MAX_CONCURRENT_PARSING),
        embed_semaphore=Semaphore(app_settings.WORKER_MAX_CONCURRENT_EMBEDDING),
    )
    
    # 6. Process file use case
    process_file = ProcessFileEvent(
        ingest_document=ingest,
        repository=repository,
    )
    
    # 7. Worker
    filewatcher_url = os.getenv("FILEWATCHER_API_URL", "http://localhost:8081")
    worker = Worker(
        db=repository,
        filewatcher_api_url=filewatcher_url,
        process_file_func=process_file,
    )
    
    return WorkerApplication(
        worker=worker,
        repository=repository,
    )


__all__ = ["WorkerApplication", "build_worker_application"]
