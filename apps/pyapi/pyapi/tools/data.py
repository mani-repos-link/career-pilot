from __future__ import annotations

import json
from typing import Any

from sqlmodel import Session, select

from pyapi.config import ToolConfig
from pyapi.store import MessageRecord, shared_engine

from .args import string_arg


def run_explain_context(config: ToolConfig, arguments: dict[str, Any], current_session_id: str | None = None) -> str:
    session_id = session_id_arg(arguments, current_session_id)
    engine = shared_engine(config.database_url)
    with Session(engine) as db:
        stmt = (
            select(MessageRecord)
            .where(MessageRecord.session_id == session_id)
            .order_by(MessageRecord.created_at.asc())
        )
        messages = list(db.exec(stmt).all())

    context_messages = active_context_messages(messages)
    payload = {
        "sessionId": session_id,
        "messageCount": len(messages),
        "activeContextMessageCount": len(context_messages),
        "rawMessagesSent": [
            {
                "id": message.id,
                "role": message.role,
                "createdAt": message.created_at.isoformat().replace("+00:00", "Z"),
                "preview": message.content[:240],
            }
            for message in context_messages
        ],
    }
    return json.dumps(payload, indent=2)


def session_id_arg(arguments: dict[str, Any], current_session_id: str | None) -> str:
    session_id = string_arg(arguments, "session_id", current_session_id or "").strip()
    if not session_id:
        raise ValueError("session_id is required")
    return session_id


def active_context_messages(messages: list[MessageRecord]) -> list[MessageRecord]:
    by_id = {message.id: message for message in messages}
    context: list[MessageRecord] = []
    for message in messages:
        if message.role == "assistant" and message.parent_message_id:
            continue
        if message.role == "user":
            context.append(message)
            if message.active_response_id and message.active_response_id in by_id:
                context.append(by_id[message.active_response_id])
            continue
        if message.role in {"assistant", "system"}:
            context.append(message)
    return context
