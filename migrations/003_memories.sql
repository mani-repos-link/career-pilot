-- Memories: durable key/value notes the agent can write/read across turns.
-- Two scopes:
--   session = tied to one sessions.id (cascades on delete)
--   global  = process-wide (no owner concept yet; single-tenant for now)
-- Partial UNIQUE indexes enforce uniqueness per scope; table-level UNIQUE would
-- mishandle NULL session_id for global rows.

CREATE TABLE IF NOT EXISTS memories (
  id         TEXT        PRIMARY KEY,
  scope      TEXT        NOT NULL CHECK (scope IN ('session','global')),
  session_id TEXT        REFERENCES sessions(id) ON DELETE CASCADE,
  key        TEXT        NOT NULL,
  content    TEXT        NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT memories_session_scope CHECK (
    (scope = 'global'  AND session_id IS NULL) OR
    (scope = 'session' AND session_id IS NOT NULL)
  )
);

CREATE UNIQUE INDEX IF NOT EXISTS memories_global_key  ON memories(key)             WHERE scope = 'global';
CREATE UNIQUE INDEX IF NOT EXISTS memories_session_key ON memories(session_id, key) WHERE scope = 'session';
CREATE INDEX        IF NOT EXISTS memories_session_idx ON memories(scope, session_id);
