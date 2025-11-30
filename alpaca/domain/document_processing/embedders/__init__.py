"""Embedders re-export."""

from app.embedders.custom_embedder import embedding as embed_chunks

__all__ = ["embed_chunks"]
