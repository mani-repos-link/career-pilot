from __future__ import annotations

from ..errors import NotFoundError
from ..ids import new_id, timestamp
from ..models import SessionRecord
from .rows import session_from_row


class SessionStoreMixin:
    def list_sessions(self) -> list[SessionRecord]:
        rows = self._query_all(
            """
            SELECT id, title, created_at, updated_at
            FROM sessions
            WHERE archived_at IS NULL
            ORDER BY updated_at DESC
            """
        )
        return [session_from_row(row) for row in rows]

    def create_session(self, title: str) -> SessionRecord:
        now = timestamp()
        session = SessionRecord(
            id=new_id("ses"),
            title=title.strip() or "New chat",
            created_at=now,
            updated_at=now,
        )
        with self._lock, self._db:
            self._db.execute(
                """
                INSERT INTO sessions (id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (session.id, session.title, session.created_at, session.updated_at),
            )
        return session

    def get_session(self, session_id: str) -> SessionRecord:
        row = self._query_one(
            """
            SELECT id, title, created_at, updated_at
            FROM sessions
            WHERE id = ? AND archived_at IS NULL
            """,
            (session_id,),
        )
        if row is None:
            raise NotFoundError("session not found")
        return session_from_row(row)

    def update_session_title(self, session_id: str, title: str) -> SessionRecord:
        title = title.strip()
        if not title:
            raise ValueError("title is required")

        with self._lock, self._db:
            cursor = self._db.execute(
                """
                UPDATE sessions
                SET title = ?
                WHERE id = ? AND archived_at IS NULL
                """,
                (title, session_id),
            )
        if cursor.rowcount == 0:
            raise NotFoundError("session not found")
        return self.get_session(session_id)

    def delete_session(self, session_id: str) -> None:
        now = timestamp()
        with self._lock, self._db:
            cursor = self._db.execute(
                """
                UPDATE sessions
                SET archived_at = ?, updated_at = ?
                WHERE id = ? AND archived_at IS NULL
                """,
                (now, now, session_id),
            )
        if cursor.rowcount == 0:
            raise NotFoundError("session not found")
