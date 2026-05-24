from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, select

from .engine import normalize_url
from .errors import NotFoundError
from .ids import new_id
from .models import MessageRecord, SessionRecord

from sqlmodel import create_engine


class Store:
    def __init__(self, database_url: str, *, create_tables: bool = False):
        self.engine: Engine = create_engine(normalize_url(database_url))
        if create_tables:
            SQLModel.metadata.create_all(self.engine)

    def close(self) -> None:
        self.engine.dispose()

    # ---------- sessions ----------

    def list_sessions(self) -> list[SessionRecord]:
        with Session(self.engine) as db:
            stmt = (
                select(SessionRecord)
                .where(SessionRecord.archived_at.is_(None))
                .order_by(SessionRecord.updated_at.desc())
            )
            return list(db.exec(stmt).all())

    def create_session(self, title: str) -> SessionRecord:
        session = SessionRecord(id=new_id("ses"), title=title.strip() or "New chat")
        with Session(self.engine) as db:
            db.add(session)
            db.commit()
            db.refresh(session)
            return session

    def get_session(self, session_id: str) -> SessionRecord:
        with Session(self.engine) as db:
            row = db.get(SessionRecord, session_id)
            if row is None or row.archived_at is not None:
                raise NotFoundError("session not found")
            return row

    def update_session_title(self, session_id: str, title: str) -> SessionRecord:
        title = title.strip()
        if not title:
            raise ValueError("title is required")
        with Session(self.engine) as db:
            row = db.get(SessionRecord, session_id)
            if row is None or row.archived_at is not None:
                raise NotFoundError("session not found")
            row.title = title
            row.updated_at = _utcnow()
            db.add(row)
            db.commit()
            db.refresh(row)
            return row

    def delete_session(self, session_id: str) -> None:
        with Session(self.engine) as db:
            row = db.get(SessionRecord, session_id)
            if row is None or row.archived_at is not None:
                raise NotFoundError("session not found")
            now = _utcnow()
            row.archived_at = now
            row.updated_at = now
            db.add(row)
            db.commit()

    # ---------- messages ----------

    def list_messages(self, session_id: str) -> list[MessageRecord]:
        self.get_session(session_id)
        with Session(self.engine) as db:
            stmt = (
                select(MessageRecord)
                .where(MessageRecord.session_id == session_id)
                .order_by(MessageRecord.created_at.asc())
            )
            return list(db.exec(stmt).all())

    def list_context_messages(
        self,
        session_id: str,
        through_user_message_id: Optional[str] = None,
    ) -> list[MessageRecord]:
        messages = self.list_messages(session_id)
        by_id = {message.id: message for message in messages}
        context: list[MessageRecord] = []

        for message in messages:
            if message.role == "assistant" and message.parent_message_id:
                continue

            if message.role == "user":
                context.append(message)
                if message.active_response_id:
                    active_response = by_id.get(message.active_response_id)
                    if active_response is not None:
                        context.append(active_response)
                if message.id == through_user_message_id:
                    break
                continue

            if message.role in {"assistant", "system"}:
                context.append(message)

        return context

    def list_messages_page(
        self,
        session_id: str,
        limit: int = 15,
        before: Optional[str | datetime] = None,
    ) -> tuple[list[MessageRecord], bool]:
        self.get_session(session_id)
        limit = max(1, limit)
        before_dt = _coerce_datetime(before)

        with Session(self.engine) as db:
            stmt = select(MessageRecord).where(MessageRecord.session_id == session_id)
            if before_dt is not None:
                stmt = stmt.where(MessageRecord.created_at < before_dt)
            stmt = stmt.order_by(MessageRecord.created_at.desc()).limit(limit + 1)
            rows = list(db.exec(stmt).all())

        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]
        return list(reversed(rows)), has_more

    def create_message(
        self,
        session_id: str,
        role: str,
        content: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        parent_message_id: Optional[str] = None,
        make_active: bool = False,
    ) -> MessageRecord:
        role = role.strip()
        content = content.strip()
        if role not in {"user", "assistant", "system", "tool"}:
            raise ValueError("invalid role")
        if not content:
            raise ValueError("content is required")
        if parent_message_id and role != "assistant":
            raise ValueError("only assistant messages can have a parent")

        with Session(self.engine) as db:
            session_row = db.get(SessionRecord, session_id)
            if session_row is None or session_row.archived_at is not None:
                raise NotFoundError("session not found")

            if parent_message_id:
                parent = db.get(MessageRecord, parent_message_id)
                if parent is None or parent.session_id != session_id:
                    raise NotFoundError("parent message not found")
                if parent.role != "user":
                    raise ValueError("assistant parent must be a user message")

            now = _utcnow()
            message = MessageRecord(
                id=new_id("msg"),
                session_id=session_id,
                role=role,
                content=content,
                provider=provider,
                model=model,
                parent_message_id=parent_message_id,
                active_response_id=None,
                created_at=now,
            )
            db.add(message)
            db.flush()

            if parent_message_id and make_active:
                parent = db.get(MessageRecord, parent_message_id)
                if parent is not None:
                    parent.active_response_id = message.id
                    db.add(parent)

            session_row.updated_at = now
            db.add(session_row)

            db.commit()
            db.refresh(message)
            return message

    def set_active_response(self, session_id: str, assistant_message_id: str) -> MessageRecord:
        with Session(self.engine) as db:
            session_row = db.get(SessionRecord, session_id)
            if session_row is None or session_row.archived_at is not None:
                raise NotFoundError("session not found")

            assistant = db.get(MessageRecord, assistant_message_id)
            if assistant is None or assistant.session_id != session_id:
                raise NotFoundError("message not found")
            if assistant.role != "assistant" or not assistant.parent_message_id:
                raise ValueError("only assistant alternatives can be activated")

            parent = db.get(MessageRecord, assistant.parent_message_id)
            if parent is not None:
                parent.active_response_id = assistant.id
                db.add(parent)

            session_row.updated_at = _utcnow()
            db.add(session_row)

            db.commit()
            db.refresh(assistant)
            return assistant


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_datetime(value: Optional[str | datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = value.strip()
    if not text:
        return None
    return datetime.fromisoformat(text.replace("Z", "+00:00"))
