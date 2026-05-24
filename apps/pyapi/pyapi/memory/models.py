from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MemoryRecord(SQLModel, table=True):
    __tablename__ = "memories"

    id: str = Field(primary_key=True)
    scope: str
    session_id: Optional[str] = Field(default=None, foreign_key="sessions.id", index=True)
    key: str
    content: str
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


SCOPE_SESSION = "session"
SCOPE_GLOBAL = "global"
VALID_SCOPES = {SCOPE_SESSION, SCOPE_GLOBAL}
