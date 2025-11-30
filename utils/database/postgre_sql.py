"""Backward-compatible import for the new Postgres repository implementation."""

from alpaca.infrastructure.database.postgres import (
    PostgresFileRepository as PostgreDataBase,
)
