"""Domain-level parser protocols decoupled from application implementations."""

from __future__ import annotations

from typing import Protocol

from core.domain.files.models import FileSnapshot


class ParserProtocol(Protocol):
    """Structural contract for parser implementations."""

    def parse(self, file: FileSnapshot) -> str:  # pragma: no cover - protocol definition
        ...


__all__ = ["ParserProtocol"]
