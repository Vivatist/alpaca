"""Embedding implementations used by the worker."""

from .custom_embedder import embedding

embed_chunks = embedding

__all__ = ["embedding", "embed_chunks"]
