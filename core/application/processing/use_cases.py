from __future__ import annotations
from typing import Optional
from dataclasses import dataclass, field
from threading import Semaphore
from typing import Dict, Any, List
import os

from utils.logging import get_logger
from core.domain.files.repository import FileRepository
from core.domain.files.models import FileSnapshot
from core.domain.document_processing import ParserRegistry, Chunker, Embedder, Cleaner


@dataclass
class IngestDocument:
    """Полный пайплайн обработки документа (parse → clean → chunk → embed)."""

    # Обязательные поля (без default)
    repository: FileRepository
    parser_registry: ParserRegistry
    chunker: Chunker
    embedder: Embedder
    parse_semaphore: Semaphore
    embed_semaphore: Semaphore
    
    # Опциональные поля (с default)
    cleaner: Optional[Cleaner] = None
    temp_dir: str = "/home/alpaca/tmp_md"
    logger_name: str = field(default="core.ingest")

    def __post_init__(self):
        self.logger = get_logger(self.logger_name)

    def __call__(self, file: FileSnapshot) -> bool:
        self.logger.info(f"🍎 Start ingest pipeline: {file.path} (hash: {file.hash[:8]}...)")
        try:
            # 1. Parse
            parser = self.parser_registry.get_parser(file.path)
            if parser is None:
                self.logger.error(f"Unsupported file type: {file.path}")
                self.repository.mark_as_error(file.hash)
                return False

            with self.parse_semaphore:
                file.raw_text = parser.parse(file)
                self.repository.set_raw_text(file.hash, file.raw_text)

            self.logger.info(f"✅ Parsed: {len(file.raw_text) if file.raw_text else 0} chars")

            # 1.1. Save to disk for debugging
            self._save_to_disk(file)
            
            # 2. Clean (если cleaner задан)        
            if self.cleaner is not None:
                file.raw_text = self.cleaner(file)
                self.logger.info(f"✅ Cleaned: {len(file.raw_text) if file.raw_text else 0} chars")

            # 3. Chunk
            chunks = self.chunker(file)
            if not chunks:
                self.logger.warning(f"No chunks created for {file.path}")
                self.repository.mark_as_error(file.hash)
                return False

            # 4. Embed
            with self.embed_semaphore:
                chunks_count = self.embedder(self.repository, file, chunks)

            if chunks_count == 0:
                self.logger.warning(f"No embeddings created for {file.path}")
                self.repository.mark_as_error(file.hash)
                return False

            # 5. Mark success
            self.repository.mark_as_ok(file.hash)
            self.logger.info(f"✅ File processed successfully: {file.path} | chunks={chunks_count}")
            return True
            
        except Exception as exc:
            import traceback
            self.logger.error(f"Pipeline failed for {file.path}: {exc}")
            self.logger.error(f"Traceback:\n{traceback.format_exc()}")
            self.repository.mark_as_error(file.hash)
            return False
    
    def _save_to_disk(self, file: FileSnapshot) -> None:
        """Save parsed text to disk for debugging."""
        if not file.raw_text:
            return
        
        temp_file_path = os.path.join(self.temp_dir, f"{file.path}.md")
        os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)
        with open(temp_file_path, "w", encoding="utf-8") as f:
            f.write(file.raw_text)
        self.logger.debug(f"💾 Saved to {temp_file_path}")


@dataclass
class ProcessFileEvent:
    """Use-case для обработки событий file_watcher'a."""

    ingest_document: IngestDocument
    repository: FileRepository
    logger_name: str = field(default="core.process_file")

    def __post_init__(self):
        self.logger = get_logger(self.logger_name)

    def __call__(self, file_info: Dict[str, Any]) -> bool:
        file = FileSnapshot(**file_info)
        self.logger.info(f"Processing file: {file.path} (status={file.status_sync})")

        try:
            if file.status_sync == "deleted":
                self.repository.delete_chunks_by_hash(file.hash)
                self.repository.delete_file_by_hash(file.hash)
                self.logger.info(f"🗑️ Deleted file and chunks: {file.path}")
                return True
            
            if file.status_sync == "updated":
                self.repository.delete_chunks_by_hash(file.hash)
                self.logger.info(f"🪓 Deleted old chunks: {file.path}")
                return self.ingest_document(file)
            
            if file.status_sync == "added":
                return self.ingest_document(file)

            self.logger.warning(f"Unknown status: {file.status_sync} for {file.path}")
            return False
            
        except Exception as exc:
            self.logger.error(f"✗ Error processing {file.path}: {exc}")
            self.repository.mark_as_error(file.hash)
            return False
