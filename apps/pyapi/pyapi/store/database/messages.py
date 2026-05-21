from __future__ import annotations

from ..errors import NotFoundError
from ..ids import new_id, timestamp
from ..models import MessageRecord
from .rows import message_from_row


class MessageStoreMixin:
    def list_messages(self, session_id: str) -> list[MessageRecord]:
        self.get_session(session_id)
        rows = self._query_all(
            """
            SELECT id, session_id, role, content, provider, model, parent_message_id, active_response_id, created_at
            FROM messages
            WHERE session_id = ?
            ORDER BY created_at ASC
            """,
            (session_id,),
        )
        return [message_from_row(row) for row in rows]

    def list_context_messages(
        self,
        session_id: str,
        through_user_message_id: str | None = None,
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
        before: str | None = None,
    ) -> tuple[list[MessageRecord], bool]:
        self.get_session(session_id)
        limit = max(1, limit)
        params: list[object] = [session_id]
        before_clause = ""
        if before:
            before_clause = "AND created_at < ?"
            params.append(before)
        params.append(limit + 1)

        rows = self._query_all(
            f"""
            SELECT id, session_id, role, content, provider, model, parent_message_id, active_response_id, created_at
            FROM messages
            WHERE session_id = ?
            {before_clause}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            tuple(params),
        )
        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]
        return [message_from_row(row) for row in reversed(rows)], has_more

    def create_message(
        self,
        session_id: str,
        role: str,
        content: str,
        provider: str | None = None,
        model: str | None = None,
        parent_message_id: str | None = None,
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

        self.get_session(session_id)
        if parent_message_id:
            parent = self._query_one(
                """
                SELECT id, role
                FROM messages
                WHERE id = ? AND session_id = ?
                """,
                (parent_message_id, session_id),
            )
            if parent is None:
                raise NotFoundError("parent message not found")
            if parent["role"] != "user":
                raise ValueError("assistant parent must be a user message")

        now = timestamp()
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

        with self._lock, self._db:
            self._db.execute(
                """
                INSERT INTO messages (id, session_id, role, content, provider, model, parent_message_id, active_response_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message.id,
                    message.session_id,
                    message.role,
                    message.content,
                    message.provider,
                    message.model,
                    message.parent_message_id,
                    message.active_response_id,
                    message.created_at,
                ),
            )
            if parent_message_id and make_active:
                self._db.execute(
                    """
                    UPDATE messages
                    SET active_response_id = ?
                    WHERE id = ? AND session_id = ?
                    """,
                    (message.id, parent_message_id, session_id),
                )
            self._db.execute(
                """
                UPDATE sessions
                SET updated_at = ?
                WHERE id = ?
                """,
                (now, session_id),
            )
        return message

    def set_active_response(self, session_id: str, assistant_message_id: str) -> MessageRecord:
        self.get_session(session_id)
        assistant = self._query_one(
            """
            SELECT id, session_id, role, content, provider, model, parent_message_id, active_response_id, created_at
            FROM messages
            WHERE id = ? AND session_id = ?
            """,
            (assistant_message_id, session_id),
        )
        if assistant is None:
            raise NotFoundError("message not found")
        if assistant["role"] != "assistant" or not assistant["parent_message_id"]:
            raise ValueError("only assistant alternatives can be activated")

        with self._lock, self._db:
            self._db.execute(
                """
                UPDATE messages
                SET active_response_id = ?
                WHERE id = ? AND session_id = ?
                """,
                (assistant_message_id, assistant["parent_message_id"], session_id),
            )
            self._db.execute(
                """
                UPDATE sessions
                SET updated_at = ?
                WHERE id = ?
                """,
                (timestamp(), session_id),
            )
        return message_from_row(assistant)

    def _ensure_message_branch_columns(self) -> None:
        columns = {row["name"] for row in self._db.execute("PRAGMA table_info(messages)").fetchall()}
        if "parent_message_id" not in columns:
            self._db.execute("ALTER TABLE messages ADD COLUMN parent_message_id TEXT")
        if "active_response_id" not in columns:
            self._db.execute("ALTER TABLE messages ADD COLUMN active_response_id TEXT")

    def _backfill_message_branches(self) -> None:
        rows = self._db.execute(
            """
            SELECT id, session_id, role, parent_message_id
            FROM messages
            ORDER BY session_id ASC, created_at ASC
            """
        ).fetchall()
        last_user_by_session: dict[str, str] = {}
        active_response_by_user: dict[str, str] = {}

        for row in rows:
            if row["role"] == "user":
                last_user_by_session[row["session_id"]] = row["id"]
                continue
            if row["role"] != "assistant" or row["parent_message_id"]:
                continue

            parent_id = last_user_by_session.get(row["session_id"])
            if not parent_id:
                continue
            self._db.execute(
                """
                UPDATE messages
                SET parent_message_id = ?
                WHERE id = ?
                """,
                (parent_id, row["id"]),
            )
            active_response_by_user[parent_id] = row["id"]

        for user_id, assistant_id in active_response_by_user.items():
            self._db.execute(
                """
                UPDATE messages
                SET active_response_id = COALESCE(active_response_id, ?)
                WHERE id = ?
                """,
                (assistant_id, user_id),
            )
