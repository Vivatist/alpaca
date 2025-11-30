"""Domain-level document processing helpers."""

from .parsers import ParserProtocol
from .parsers.registry import (
    ParserFactory,
    RegistryConfig,
    ParserRegistry,
    configure_parser_registry,
    get_parser_for_path,
)
from .chunkers import Chunker, set_chunker, get_chunker, chunk_document
from .embedders import Embedder, set_embedder, get_embedder, embed_chunks

__all__ = [
    "ParserProtocol",
    "ParserFactory",
    "RegistryConfig",
    "ParserRegistry",
    "configure_parser_registry",
    "get_parser_for_path",
    "Chunker",
    "set_chunker",
    "get_chunker",
    "chunk_document",
    "Embedder",
    "set_embedder",
    "get_embedder",
    "embed_chunks",
]
