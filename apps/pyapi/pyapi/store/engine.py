from __future__ import annotations

from functools import lru_cache

from sqlalchemy.engine import Engine
from sqlmodel import create_engine


def normalize_url(database_url: str) -> str:
    """Normalize DB URLs to SQLAlchemy form using installed drivers."""
    if database_url.startswith("file:"):
        path = database_url.removeprefix("file:").split("?", 1)[0]
        if path == ":memory:":
            return "sqlite://"
        return f"sqlite:///{path}"
    if database_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + database_url.removeprefix("postgresql://")
    if database_url.startswith("postgres://"):
        return "postgresql+psycopg://" + database_url.removeprefix("postgres://")
    return database_url


@lru_cache(maxsize=8)
def shared_engine(database_url: str) -> Engine:
    return create_engine(normalize_url(database_url))
