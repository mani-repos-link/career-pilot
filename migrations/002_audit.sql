-- Audit tables: every orchestrator delegation and every tool execution.
-- Lets us debug bad runs, replay decisions, and learn per-portal failure modes.

CREATE TABLE IF NOT EXISTS agent_runs (
  id                 TEXT        PRIMARY KEY,
  session_id         TEXT        REFERENCES sessions(id) ON DELETE CASCADE,
  parent_message_id  TEXT        REFERENCES messages(id) ON DELETE SET NULL,
  agent_name         TEXT        NOT NULL,
  instruction        TEXT        NOT NULL,
  output             TEXT,
  provider           TEXT,
  model              TEXT,
  status             TEXT        NOT NULL CHECK (status IN ('running','ok','error')),
  error              TEXT,
  started_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at        TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS tool_calls (
  id           TEXT        PRIMARY KEY,
  session_id   TEXT        REFERENCES sessions(id) ON DELETE CASCADE,
  message_id   TEXT        REFERENCES messages(id) ON DELETE SET NULL,
  agent_name   TEXT,
  tool_name    TEXT        NOT NULL,
  args         JSONB       NOT NULL DEFAULT '{}'::jsonb,
  result       JSONB,
  ok           BOOLEAN     NOT NULL,
  duration_ms  INTEGER,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_session ON agent_runs(session_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_tool_calls_session ON tool_calls(session_id, created_at DESC);
