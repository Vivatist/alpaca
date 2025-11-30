"""Parser registry exposed at domain level."""

from __future__ import annotations

from typing import Callable, Optional, Tuple

from . import ParserProtocol

ParserFactory = Callable[[], ParserProtocol]
RegistryConfig = Tuple[Tuple[Tuple[str, ...], ParserFactory], ...]


class ParserRegistry:
    """Simple factory that returns parser instances by file extension."""

    def __init__(self, registry: RegistryConfig):
        self._registry = registry

    def get_parser(self, file_path: str) -> Optional[ParserProtocol]:
        lower_path = file_path.lower()
        for extensions, factory in self._registry:
            if lower_path.endswith(extensions):
                return factory()
        return None


_parser_registry: Optional[ParserRegistry] = None


def configure_parser_registry(registry: ParserRegistry) -> None:
    """Registers parser registry supplied by application bootstrap."""

    global _parser_registry
    _parser_registry = registry


def get_parser_for_path(file_path: str) -> Optional[ParserProtocol]:
    """Returns parser for provided path or raises if registry is not ready."""

    if _parser_registry is None:
        raise RuntimeError("Parser registry is not configured")
    return _parser_registry.get_parser(file_path)


__all__ = [
    "ParserFactory",
    "RegistryConfig",
    "ParserRegistry",
    "configure_parser_registry",
    "get_parser_for_path",
]
