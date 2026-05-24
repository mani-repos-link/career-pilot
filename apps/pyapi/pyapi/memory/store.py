from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import or_
from sqlmodel import Session, SQLModel, select

from pyapi.store.engine import shared_engine
from pyapi.store.ids import new_id

from .models import SCOPE_GLOBAL, SCOPE_SESSION, VALID_SCOPES, MemoryRecord


class MemoryStore:
    """CRUD over the memories table. Reuses the shared engine for the configured DB URL.

    Scopes:
      - 'session' requires a session_id; ON DELETE CASCADE wipes them with the session.
      - 'global'  has session_id IS NULL; survives session deletion.
    """

    def __init__(self, database_url: str, *, create_tables: bool = False):
        self.engine = shared_engine(database_url)
        if create_tables:
            SQLModel.metadata.create_all(self.engine)

    def list(self, session_id: str, *, include_global: bool = True) -> list[MemoryRecord]:
        with Session(self.engine) as db:
            if include_global:
                stmt = select(MemoryRecord).where(
                    or_(
                        (MemoryRecord.scope == SCOPE_SESSION) & (MemoryRecord.session_id == session_id),
                        MemoryRecord.scope == SCOPE_GLOBAL,
                    )
                ).order_by(MemoryRecord.updated_at.asc())
            else:
                stmt = select(MemoryRecord).where(
                    MemoryRecord.scope == SCOPE_SESSION,
                    MemoryRecord.session_id == session_id,
                ).order_by(MemoryRecord.updated_at.asc())
            return list(db.exec(stmt).all())

    def get(self, scope: str, session_id: str | None, key: str) -> MemoryRecord | None:
        _check_scope_args(scope, session_id)
        with Session(self.engine) as db:
            stmt = select(MemoryRecord).where(
                MemoryRecord.scope == scope,
                MemoryRecord.key == key,
            )
            if scope == SCOPE_SESSION:
                stmt = stmt.where(MemoryRecord.session_id == session_id)
            else:
                stmt = stmt.where(MemoryRecord.session_id.is_(None))
            return db.exec(stmt).first()

    def upsert(self, scope: str, session_id: str | None, key: str, content: str) -> MemoryRecord:
        _check_scope_args(scope, session_id)
        now = datetime.now(timezone.utc)
        with Session(self.engine) as db:
            existing = self.get(scope, session_id, key)
            if existing is not None:
                row = db.get(MemoryRecord, existing.id)
                assert row is not None
                row.content = content
                row.updated_at = now
                db.add(row)
                db.commit()
                db.refresh(row)
                return row
            row = MemoryRecord(
                id=new_id("mem"),
                scope=scope,
                session_id=session_id,
                key=key,
                content=content,
                created_at=now,
                updated_at=now,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return row

    def delete(self, scope: str, session_id: str | None, key: str) -> bool:
        _check_scope_args(scope, session_id)
        existing = self.get(scope, session_id, key)
        if existing is None:
            return False
        with Session(self.engine) as db:
            row = db.get(MemoryRecord, existing.id)
            if row is None:
                return False
            db.delete(row)
            db.commit()
            return True


def _check_scope_args(scope: str, session_id: str | None) -> None:
    if scope not in VALID_SCOPES:
        raise ValueError(f"invalid scope {scope!r}; expected one of {sorted(VALID_SCOPES)}")
    if scope == SCOPE_SESSION and not session_id:
        raise ValueError("session scope requires session_id")
    if scope == SCOPE_GLOBAL and session_id is not None:
        raise ValueError("global scope must not have session_id")
