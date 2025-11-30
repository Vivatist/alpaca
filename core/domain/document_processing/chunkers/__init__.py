"""Domain-level chunker type definition."""

from __future__ import annotations

from typing import Callable, List

from core.domain.files.models import FileSnapshot

Chunker = Callable[[FileSnapshot], List[str]]

__all__ = ["Chunker"]
