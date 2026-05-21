from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SessionRecord:
    id: str
    title: str
    created_at: str
    updated_at: str

    def to_api(self) -> dict[str, str]:
        return {
            "id": self.id,
            "title": self.title,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }


@dataclass(frozen=True)
class MessageRecord:
    id: str
    session_id: str
    role: str
    content: str
    provider: str | None
    model: str | None
    parent_message_id: str | None
    active_response_id: str | None
    created_at: str

    def to_api(self) -> dict[str, str | None]:
        return {
            "id": self.id,
            "sessionId": self.session_id,
            "role": self.role,
            "content": self.content,
            "provider": self.provider,
            "model": self.model,
            "parentMessageId": self.parent_message_id,
            "activeResponseId": self.active_response_id,
            "createdAt": self.created_at,
        }


