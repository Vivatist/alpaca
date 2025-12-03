"""
IngestDocument - полный пайплайн обработки документа.

Шаги:
1. Parse - извлечение текста из документа
2. Clean - очистка текста (optional)
3. MetaExtract - извлечение метаданных (optional)
4. Chunk - разбиение на части
5. Embed - создание векторов и сохранение в БД
"""

from __future__ import annotations
import os
from dataclasses import dataclass, field
from threading import Semaphore
from typing import Optional, Callable, Dict, Any, List

from logging_config import get_logger
from contracts import (
    FileSnapshot, 
    Repository, 
    ParserRegistry, 
    Chunker, 
    Embedder, 
    MetaExtractor
)
from settings import settings


@dataclass
class IngestDocument:
    """Полный пайплайн обработки документа."""
    
    # Обязательные компоненты
    repository: Repository
    parser_registry: ParserRegistry
    chunker: Chunker
    embedder: Embedder
    parse_semaphore: Semaphore
    embed_semaphore: Semaphore
    
    # Опциональные компоненты
    cleaner: Optional[Callable[[str], str]] = None
    metaextractor: Optional[MetaExtractor] = None
    temp_dir: str = field(default_factory=lambda: settings.TMP_MD_PATH)
    logger_name: str = field(default="ingest.pipeline")
    
    def __post_init__(self):
        self.logger = get_logger(self.logger_name)
    
    def __call__(self, file: FileSnapshot) -> bool:
        """
        Обработка файла через весь пайплайн.
        
        Args:
            file: FileSnapshot с информацией о файле
            
        Returns:
            True если обработка успешна
        """
        self.logger.info(f"🍎 Start ingest pipeline | file={file.path} hash={file.hash[:8]}...")
        
        try:
            # 1. Parse
            parser = self.parser_registry.get_parser(file.path)
            if parser is None:
                self.logger.error(f"Unsupported file type | file={file.path}")
                self.repository.mark_as_error(file.hash)
                return False
            
            with self.parse_semaphore:
                file.raw_text = parser.parse(file)
                self.repository.set_raw_text(file.hash, file.raw_text)
            
            self.logger.info(f"✅ Parsed | chars={len(file.raw_text) if file.raw_text else 0}")
            
            # 1.1. Save to disk for debugging
            self._save_to_disk(file)
            
            # 2. Clean (если cleaner задан)
            if self.cleaner is not None:
                file.raw_text = self.cleaner(file.raw_text)
                self.logger.info(f"✅ Cleaned | chars={len(file.raw_text) if file.raw_text else 0}")
            
            # 3. Extract metadata (если metaextractor задан)
            if self.metaextractor is not None:
                file.metadata = self.metaextractor(file)
                self.logger.info(f"✅ Metadata | keys={list(file.metadata.keys()) if file.metadata else []}")
            else:
                file.metadata = {}
            
            # 4. Chunk
            chunks = self.chunker(file)
            if not chunks:
                self.logger.warning(f"No chunks created | file={file.path}")
                self.repository.mark_as_error(file.hash)
                return False
            
            self.logger.info(f"✅ Chunked | count={len(chunks)}")
            
            # 5. Embed
            with self.embed_semaphore:
                chunks_count = self.embedder(self.repository, file, chunks, file.metadata)
            
            if chunks_count == 0:
                self.logger.warning(f"No embeddings created | file={file.path}")
                self.repository.mark_as_error(file.hash)
                return False
            
            # 6. Mark success
            self.repository.mark_as_ok(file.hash)
            self.logger.info(f"✅ File processed successfully | file={file.path} chunks={chunks_count}")
            return True
            
        except Exception as exc:
            import traceback
            self.logger.error(f"Pipeline failed | file={file.path} error={exc}")
            self.logger.error(f"Traceback:\n{traceback.format_exc()}")
            self.repository.mark_as_error(file.hash)
            return False
    
    def _save_to_disk(self, file: FileSnapshot) -> None:
        """Сохранение распарсенного текста для отладки."""
        if not file.raw_text:
            return
        
        try:
            temp_file_path = os.path.join(self.temp_dir, f"{file.path}.md")
            os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)
            with open(temp_file_path, "w", encoding="utf-8") as f:
                f.write(file.raw_text)
            self.logger.debug(f"💾 Saved to {temp_file_path}")
        except Exception as e:
            self.logger.warning(f"Failed to save debug file | error={e}")
