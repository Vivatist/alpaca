"""Domain-level chunker facade with late binding to implementations."""

from __future__ import annotations

from typing import Callable, List, Optional

from core.domain.files.models import FileSnapshot

Chunker = Callable[[FileSnapshot], List[str]]

_chunker: Optional[Chunker] = None


def set_chunker(chunker: Chunker) -> None:
	"""Registers active chunker implementation provided by the application layer."""

	global _chunker
	_chunker = chunker


def get_chunker() -> Chunker:
	"""Returns currently registered chunker or raises if missing."""

	if _chunker is None:
		raise RuntimeError("Chunker is not configured")
	return _chunker


def chunk_document(file: FileSnapshot) -> List[str]:
	"""Convenience wrapper used by legacy callers."""

	return get_chunker()(file)


__all__ = ["Chunker", "set_chunker", "get_chunker", "chunk_document"]
