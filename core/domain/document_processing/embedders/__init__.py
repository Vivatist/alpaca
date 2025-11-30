"""Domain-level embedder facade with runtime configuration."""

from __future__ import annotations

from typing import Callable, List, Optional

from core.domain.files.models import FileSnapshot
from core.domain.files.repository import Database

Embedder = Callable[[Database, FileSnapshot, List[str]], int]

_embedder: Optional[Embedder] = None


def set_embedder(embedder: Embedder) -> None:
	"""Registers active embedder implementation provided by application layer."""

	global _embedder
	_embedder = embedder


def get_embedder() -> Embedder:
	"""Returns configured embedder or raises if it is missing."""

	if _embedder is None:
		raise RuntimeError("Embedder is not configured")
	return _embedder


def embed_chunks(db: Database, file: FileSnapshot, chunks: List[str]) -> int:
	"""Legacy-compatible entry point for embedding chunks."""

	return get_embedder()(db, file, chunks)


__all__ = ["Embedder", "set_embedder", "get_embedder", "embed_chunks"]
