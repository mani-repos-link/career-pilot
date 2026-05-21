from __future__ import annotations

import sqlite3

from ..models import MessageRecord, SessionRecord


def session_from_row(row: sqlite3.Row) -> SessionRecord:
    return SessionRecord(
        id=row["id"],
        title=row["title"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def message_from_row(row: sqlite3.Row) -> MessageRecord:
    return MessageRecord(
        id=row["id"],
        session_id=row["session_id"],
        role=row["role"],
        content=row["content"],
        provider=row["provider"],
        model=row["model"],
        parent_message_id=row["parent_message_id"],
        active_response_id=row["active_response_id"],
        created_at=row["created_at"],
    )
