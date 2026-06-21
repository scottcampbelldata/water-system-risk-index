"""SQLAlchemy engine built from environment-driven settings."""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import Engine, create_engine

from waterapi.config import settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return a process-wide SQLAlchemy engine (sync psycopg driver)."""
    return create_engine(
        settings.sqlalchemy_url,
        future=True,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
