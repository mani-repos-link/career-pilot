from __future__ import annotations

import sqlite3
from threading import RLock

from .messages import MessageStoreMixin
from .schema import SCHEMA_SQL, ensure_sqlite_dir
from .sessions import SessionStoreMixin


class Store(
    SessionStoreMixin,
    MessageStoreMixin,
):
    def __init__(self, database_url: str):
        ensure_sqlite_dir(database_url)
        self._db = sqlite3.connect(database_url, uri=database_url.startswith("file:"), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = RLock()
        self.migrate()

    def close(self) -> None:
        self._db.close()

    def migrate(self) -> None:
        with self._lock, self._db:
            self._db.executescript(SCHEMA_SQL)
            self._ensure_message_branch_columns()
            self._db.execute("CREATE INDEX IF NOT EXISTS idx_messages_parent_message_id ON messages(parent_message_id)")
            self._backfill_message_branches()

    def _query_one(self, query: str, params: tuple[object, ...] = ()) -> sqlite3.Row | None:
        with self._lock:
            return self._db.execute(query, params).fetchone()

    def _query_all(self, query: str, params: tuple[object, ...] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return list(self._db.execute(query, params).fetchall())
