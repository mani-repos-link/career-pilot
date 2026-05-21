from __future__ import annotations

from pathlib import Path


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  archived_at TEXT
);

CREATE TABLE IF NOT EXISTS messages (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool')),
  content TEXT NOT NULL,
  provider TEXT,
  model TEXT,
  parent_message_id TEXT,
  active_response_id TEXT,
  token_count INTEGER,
  created_at TEXT NOT NULL,
  FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
  FOREIGN KEY (parent_message_id) REFERENCES messages(id) ON DELETE SET NULL,
  FOREIGN KEY (active_response_id) REFERENCES messages(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON sessions(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_session_created_at ON messages(session_id, created_at ASC);
"""


def ensure_sqlite_dir(database_url: str) -> None:
    if not database_url.startswith("file:"):
        return

    path = database_url.removeprefix("file:").split("?", 1)[0]
    if not path or path == ":memory:":
        return

    directory = Path(path).parent
    if str(directory) not in {"", "."}:
        directory.mkdir(parents=True, exist_ok=True)
