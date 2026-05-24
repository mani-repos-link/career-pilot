-- Career Pilot — initial schema (Postgres 18 + pgvector + PostGIS allowed).
-- Ports the SQLite tables (sessions, messages) used by the chatbot fork.

CREATE TABLE IF NOT EXISTS sessions (
  id          TEXT        PRIMARY KEY,
  title       TEXT        NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  archived_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS messages (
  id                  TEXT        PRIMARY KEY,
  session_id          TEXT        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  role                TEXT        NOT NULL CHECK (role IN ('user','assistant','system','tool')),
  content             TEXT        NOT NULL,
  provider            TEXT,
  model               TEXT,
  parent_message_id   TEXT        REFERENCES messages(id) ON DELETE SET NULL,
  active_response_id  TEXT        REFERENCES messages(id) ON DELETE SET NULL,
  token_count         INTEGER,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sessions_updated_at         ON sessions(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_session_created_at ON messages(session_id, created_at ASC);
