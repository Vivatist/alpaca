from __future__ import annotations

from dataclasses import dataclass, field
from threading import Semaphore
from typing import Callable, Dict, Any, List, Optional

from utils.logging import get_logger
from alpaca.domain.files.repository import Database
from alpaca.domain.files.models import FileSnapshot
from alpaca.application.files.services import FileService
from alpaca.application.document_processing.parsers import BaseParser

ParserResolver = Callable[[str], Optional[BaseParser]]
Chunker = Callable[[FileSnapshot], List[str]]
Embedder = Callable[[Database, FileSnapshot, List[str]], int]


@dataclass
class IngestDocument:
    """Полный пайплайн обработки документа (parse → chunk → embed)."""

    file_service: FileService
    database: Database
    parser_resolver: ParserResolver
    chunker: Chunker
    embedder: Embedder
    parse_semaphore: Semaphore
    embed_semaphore: Semaphore
    logger_name: str = field(default="alpaca.ingest")

    def __post_init__(self):
        self.logger = get_logger(self.logger_name)

    def __call__(self, file: FileSnapshot) -> bool:
        self.logger.info(f"🍎 Start ingest pipeline: {file.path} (hash: {file.hash[:8]}...)")
        try:
            parser = self.parser_resolver(file.path)
            if parser is None:
                self.logger.error(f"Unsupported file type: {file.path}")
                self.file_service.mark_as_error(file)
                return False

            with self.parse_semaphore:
                file.raw_text = parser.parse(file)
                self.file_service.set_raw_text(file, file.raw_text)

            self.logger.info(f"✅ Parsed: {len(file.raw_text) if file.raw_text else 0} chars")

            self.file_service.save_file_to_disk(file)

            chunks = self.chunker(file)
            if not chunks:
                self.logger.warning(f"No chunks created for {file.path}")
                self.file_service.mark_as_error(file)
                return False

            with self.embed_semaphore:
                chunks_count = self.embedder(self.database, file, chunks)

            if chunks_count == 0:
                self.logger.warning(f"No embeddings created for {file.path}")
                self.file_service.mark_as_error(file)
                return False

            self.file_service.mark_as_ok(file)
            self.logger.info(
                f"✅ File processed successfully: {file.path} | chunks={chunks_count}"
            )
            return True
        except Exception as exc:  # pragma: no cover - defensive logging
            import traceback

            self.logger.error(f"Pipeline failed for {file.path}: {exc}")
            self.logger.error(f"Traceback:\n{traceback.format_exc()}")
            self.file_service.mark_as_error(file)
            return False


@dataclass
class ProcessFileEvent:
    """Use-case для обработки событий file_watcher'a."""

    ingest_document: IngestDocument
    file_service: FileService
    logger_name: str = field(default="alpaca.process_file")

    def __post_init__(self):
        self.logger = get_logger(self.logger_name)

    def __call__(self, file_info: Dict[str, Any]) -> bool:
        file = FileSnapshot(**file_info)
        self.logger.info(f"Processing file: {file.path} (status={file.status_sync})")

        try:
            if file.status_sync == "deleted":
                self.file_service.delete_file_and_chunks(file)
                return True
            if file.status_sync == "updated":
                self.file_service.delete_chunks_only(file)
                return self.ingest_document(file)
            if file.status_sync == "added":
                return self.ingest_document(file)

            self.logger.warning(f"Unknown status: {file.status_sync} for {file.path}")
            return False
        except Exception as exc:  # pragma: no cover - defensive logging
            self.logger.error(f"✗ Error processing {file.path}: {exc}")
            self.file_service.mark_as_error(file)
            return False
