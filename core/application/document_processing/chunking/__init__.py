"""Chunking implementations used by the worker."""

from .custom_chunker import chunking

chunk_document = chunking

__all__ = ["chunking", "chunk_document"]
