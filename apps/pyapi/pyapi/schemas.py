from __future__ import annotations

from pydantic import BaseModel


class Session(BaseModel):
    id: str
    title: str
    createdAt: str
    updatedAt: str


class Message(BaseModel):
    id: str
    sessionId: str
    role: str
    content: str
    provider: str | None = None
    model: str | None = None
    createdAt: str


class CreateSessionRequest(BaseModel):
    title: str = "New chat"


class UpdateSessionRequest(BaseModel):
    title: str


class CreateMessageRequest(BaseModel):
    role: str
    content: str
