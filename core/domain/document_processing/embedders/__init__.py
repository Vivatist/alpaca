"""Domain-level embedder type definition."""

from __future__ import annotations

from typing import Callable, List

from core.domain.files.models import FileSnapshot
from core.domain.files.repository import FileRepository

Embedder = Callable[[FileRepository, FileSnapshot, List[str]], int]

__all__ = ["Embedder"]
