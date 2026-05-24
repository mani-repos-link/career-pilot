from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel

from pyapi.providers.turn import Turn


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class SessionRecord(SQLModel, table=True):
    __tablename__ = "sessions"

    id: str = Field(primary_key=True)
    title: str
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    archived_at: Optional[datetime] = None

    def to_api(self) -> dict[str, str]:
        return {
            "id": self.id,
            "title": self.title,
            "createdAt": _iso(self.created_at),
            "updatedAt": _iso(self.updated_at),
        }


class MessageRecord(SQLModel, table=True):
    __tablename__ = "messages"

    id: str = Field(primary_key=True)
    session_id: str = Field(foreign_key="sessions.id", index=True)
    role: str
    content: str
    provider: Optional[str] = None
    model: Optional[str] = None
    parent_message_id: Optional[str] = Field(default=None, foreign_key="messages.id")
    active_response_id: Optional[str] = Field(default=None, foreign_key="messages.id")
    token_count: Optional[int] = None
    created_at: datetime = Field(default_factory=_utcnow)

    def to_api(self) -> dict[str, Optional[str]]:
        return {
            "id": self.id,
            "sessionId": self.session_id,
            "role": self.role,
            "content": self.content,
            "provider": self.provider,
            "model": self.model,
            "parentMessageId": self.parent_message_id,
            "activeResponseId": self.active_response_id,
            "createdAt": _iso(self.created_at),
        }

    def to_turn(self) -> Turn:
        return Turn(role=self.role, content=self.content)
