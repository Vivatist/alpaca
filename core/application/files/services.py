from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

from settings import settings
from utils.logging import get_logger

from core.domain.files.models import FileSnapshot
from core.domain.files.repository import FileRepository


@dataclass
class FileService:
    """High-level file + chunk operations backed by a FileRepository."""

    repository: FileRepository
    temp_dir: str = field(default_factory=lambda: getattr(settings, "TEMP_PARSED_DIR", "/home/alpaca/tmp_md"))
    logger_name: str = field(default="core.file-service")

    def __post_init__(self) -> None:
        self.logger = get_logger(self.logger_name)

    # --- Status helpers -----------------------------------------------------
    def mark_as_processed(self, file: FileSnapshot) -> None:
        self.repository.mark_as_processed(file.hash)
        self.logger.debug("Файл помечен как processed | hash=%s path=%s", file.hash, file.path)

    def mark_as_ok(self, file: FileSnapshot) -> None:
        self.repository.mark_as_ok(file.hash)
        self.logger.info("✅ Файл успешно обработан | hash=%s path=%s", file.hash, file.path)

    def mark_as_error(self, file: FileSnapshot) -> None:
        self.repository.mark_as_error(file.hash)
        self.logger.error("❌ Файл помечен как error | hash=%s path=%s", file.hash, file.path)

    def set_raw_text(self, file: FileSnapshot, raw_text: str) -> None:
        self.repository.set_raw_text(file.hash, raw_text)
        self.logger.debug("Сохранён raw_text | hash=%s path=%s length=%s", file.hash, file.path, len(raw_text))

    # --- Chunk + file lifecycle --------------------------------------------
    def delete_file_and_chunks(self, file: FileSnapshot) -> None:
        deleted_chunks_count = self._delete_chunks(file)
        self.repository.delete_file_by_hash(file.hash)
        self.logger.info("🗑️ Файл и чанки удалены | path=%s deleted_chunks=%s", file.path, deleted_chunks_count)

    def delete_chunks_only(self, file: FileSnapshot) -> int:
        deleted_count = self._delete_chunks(file)
        self.logger.info("🪓 Удалены только чанки | path=%s count=%s", file.path, deleted_count)
        return deleted_count

    def save_file_to_disk(self, file: FileSnapshot) -> str:
        if not file.raw_text:
            self.logger.debug("Нет raw_text для сохранения | path=%s", file.path)
            return ""

        temp_file_path = os.path.join(self.temp_dir, f"{file.path}.md")
        os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)
        with open(temp_file_path, "w", encoding="utf-8") as handle:
            handle.write(file.raw_text)
        self.logger.debug("💾 Распарсенный текст сохранён | path=%s length=%s", temp_file_path, len(file.raw_text))
        return temp_file_path

    # --- Internal helpers ---------------------------------------------------
    def _delete_chunks(self, file: FileSnapshot) -> int:
        deleted_by_hash = self.repository.delete_chunks_by_hash(file.hash)
        deleted_total = deleted_by_hash

        deleted_by_path = self.repository.delete_chunks_by_path(file.path)
        if deleted_by_path:
            deleted_total += deleted_by_path
            self.logger.debug(
                "Удалены остаточные чанки по пути | path=%s hash=%s fallback=%s",
                file.path,
                file.hash,
                deleted_by_path,
            )
        else:
            self.logger.debug(
                "Чанки удалены по хэшу | path=%s hash=%s count=%s",
                file.path,
                file.hash,
                deleted_by_hash,
            )

        return deleted_total
