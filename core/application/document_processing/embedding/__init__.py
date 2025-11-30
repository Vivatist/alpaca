"""Embedding implementations used by the worker."""

from .custom_embedder import custom_embedding
from .langchain_embedder import langchain_embedding

embed_chunks = custom_embedding

__all__ = ["custom_embedding", "langchain_embedding", "embed_chunks"]