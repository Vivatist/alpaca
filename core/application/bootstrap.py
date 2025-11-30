from __future__ import annotations

import os
from dataclasses import dataclass
from threading import Semaphore
from typing import Optional

from settings import Settings, settings
from core.application.document_processing.parsers import (
    WordParser,
    PDFParser,
    PowerPointParser,
    ExcelParser,
    TXTParser,
)
from core.application.document_processing.chunking import chunk_document as default_chunker_impl
from core.application.document_processing.embedding import custom_embedding, langchain_embedding
from core.application.files.services import FileService
from core.application.processing import IngestDocument, ProcessFileEvent
from core.application.processing.use_cases import ParserResolver, Chunker, Embedder
from core.domain.document_processing import (
    ParserRegistry,
    configure_parser_registry,
    get_parser_for_path,
    set_chunker,
    set_embedder,
)
from core.infrastructure.database.postgres import PostgresFileRepository
from utils.worker import Worker

DOC_EXTENSIONS = (".doc", ".docx")
FILEWATCHER_ENV_VAR = "FILEWATCHER_API_URL"
DEFAULT_FILEWATCHER_URL = "http://localhost:8081"


@dataclass
class WorkerApplication:
    """Собранные компоненты worker с единым bootstrap."""

    settings: Settings
    repository: PostgresFileRepository
    file_service: FileService
    parser_resolver: ParserResolver
    ingest_document: IngestDocument
    process_file_event: ProcessFileEvent
    worker: Worker
    word_parser: WordParser
    chunker: Chunker
    embedder: Embedder


def build_repository(app_settings: Settings = settings) -> PostgresFileRepository:
    """Создаёт репозиторий с учётом настроек таблиц."""

    return PostgresFileRepository(
        database_url=app_settings.DATABASE_URL,
        files_table=getattr(app_settings, "FILES_TABLE_NAME", "files"),
    )


def build_word_parser() -> WordParser:
    """Фабрика word-парсера с OCR."""

    return WordParser(enable_ocr=True)


def build_chunker() -> Chunker:
    """Фабрика chunker'а (можно расширить через настройки позже)."""

    return default_chunker_impl


def build_parser_resolver(word_parser: Optional[WordParser] = None) -> ParserResolver:
    """Создаёт resolver, который для doc/docx использует общий WordParser."""

    parser = word_parser or build_word_parser()

    def resolver(file_path: str):
        lower = file_path.lower()
        if lower.endswith(DOC_EXTENSIONS):
            return parser
        return get_parser_for_path(file_path)

    return resolver


def _resolve_embedder(app_settings: Settings) -> Embedder:
    """Позволяет в будущем выбирать разные embedders через настройки."""

    backend = getattr(app_settings, "EMBEDDER_BACKEND", None)
    if backend == "custom" or backend is None:
        return custom_embedding
    if backend == "langchain":  # pragma: no cover - optional dependency
        return langchain_embedding
    raise ValueError(f"Unsupported EMBEDDER_BACKEND: {backend}")


def build_ingest_document(
    app_settings: Settings,
    repository: PostgresFileRepository,
    file_service: FileService,
    parser_resolver: ParserResolver,
    *,
    chunker: Chunker,
    embedder: Optional[Embedder] = None,
) -> IngestDocument:
    """Собирает пайплайн IngestDocument с семафорами."""

    parse_semaphore = Semaphore(app_settings.WORKER_MAX_CONCURRENT_PARSING)
    embed_semaphore = Semaphore(app_settings.WORKER_MAX_CONCURRENT_EMBEDDING)

    return IngestDocument(
        file_service=file_service,
        database=repository,
        parser_resolver=parser_resolver,
        chunker=chunker,
        embedder=embedder or _resolve_embedder(app_settings),
        parse_semaphore=parse_semaphore,
        embed_semaphore=embed_semaphore,
    )


def build_process_file_use_case(
    ingest_document: IngestDocument,
    file_service: FileService,
) -> ProcessFileEvent:
    return ProcessFileEvent(
        ingest_document=ingest_document,
        file_service=file_service,
    )


def build_worker(
    repository: PostgresFileRepository,
    process_file_use_case: ProcessFileEvent,
    *,
    filewatcher_api_url: Optional[str] = None,
) -> Worker:
    api_url = filewatcher_api_url or os.getenv(FILEWATCHER_ENV_VAR, DEFAULT_FILEWATCHER_URL)
    return Worker(
        db=repository,
        filewatcher_api_url=api_url,
        process_file_func=process_file_use_case,
    )


def build_worker_application(
    app_settings: Settings = settings,
    *,
    filewatcher_api_url: Optional[str] = None,
) -> WorkerApplication:
    """Полный bootstrap worker с зависимостями."""

    repository = build_repository(app_settings)
    file_service = FileService(repository)
    word_parser = build_word_parser()
    chunker = build_chunker()
    embedder = _resolve_embedder(app_settings)
    _configure_document_processing_facade(word_parser, chunker, embedder)
    parser_resolver = build_parser_resolver(word_parser)
    ingest_document = build_ingest_document(
        app_settings,
        repository,
        file_service,
        parser_resolver,
        chunker=chunker,
        embedder=embedder,
    )
    process_file_use_case = build_process_file_use_case(ingest_document, file_service)
    worker = build_worker(
        repository,
        process_file_use_case,
        filewatcher_api_url=filewatcher_api_url,
    )

    return WorkerApplication(
        settings=app_settings,
        repository=repository,
        file_service=file_service,
        parser_resolver=parser_resolver,
        ingest_document=ingest_document,
        process_file_event=process_file_use_case,
        worker=worker,
        word_parser=word_parser,
        chunker=chunker,
        embedder=ingest_document.embedder,
    )


def _configure_document_processing_facade(
    word_parser: WordParser,
    chunker: Chunker,
    embedder: Embedder,
) -> None:
    """Готовит доменный фасад (registry + chunker/embedder aliases)."""

    configure_parser_registry(_build_parser_registry(word_parser))
    set_chunker(chunker)
    set_embedder(embedder)


def _build_parser_registry(word_parser: WordParser) -> ParserRegistry:
    """Создаёт registry с маппингами расширений на парсеры."""

    def _reuse(parser: WordParser):
        return lambda parser=parser: parser

    return ParserRegistry(
        registry=(
            (DOC_EXTENSIONS, _reuse(word_parser)),
            ((".pdf",), PDFParser),
            ((".pptx", ".ppt"), PowerPointParser),
            ((".xlsx", ".xls"), ExcelParser),
            ((".txt",), TXTParser),
        ),
    )


__all__ = [
    "WorkerApplication",
    "build_repository",
    "build_word_parser",
    "build_chunker",
    "build_parser_resolver",
    "build_ingest_document",
    "build_process_file_use_case",
    "build_worker",
    "build_worker_application",
]
