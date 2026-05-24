-- Career Pilot — job hunt domain tables.
-- Owned by job_scout (writes jobs + jds), tracker (writes applications), resume_tailor (writes resumes).

CREATE TABLE IF NOT EXISTS jobs (
  id            TEXT        PRIMARY KEY,
  portal        TEXT        NOT NULL,
  external_id   TEXT,
  url           TEXT        NOT NULL,
  title         TEXT        NOT NULL,
  company       TEXT,
  location      TEXT,
  salary_min    NUMERIC,
  salary_max    NUMERIC,
  salary_currency TEXT,
  posted_at     TIMESTAMPTZ,
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  raw_meta      JSONB       NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE (portal, external_id)
);

CREATE INDEX IF NOT EXISTS idx_jobs_first_seen_at ON jobs(first_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_portal_company ON jobs(portal, company);

CREATE TABLE IF NOT EXISTS jds (
  id           TEXT        PRIMARY KEY,
  job_id       TEXT        REFERENCES jobs(id) ON DELETE CASCADE,
  source_url   TEXT,
  raw_text     TEXT        NOT NULL,
  parsed       JSONB       NOT NULL DEFAULT '{}'::jsonb,
  fetched_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_jds_job_id ON jds(job_id);

CREATE TABLE IF NOT EXISTS resumes (
  id              TEXT        PRIMARY KEY,
  slug            TEXT        NOT NULL,
  job_id          TEXT        REFERENCES jobs(id) ON DELETE SET NULL,
  markdown_path   TEXT,
  html_path       TEXT,
  pdf_path        TEXT,
  cover_letter_md TEXT,
  cover_letter_pdf TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_resumes_job_id ON resumes(job_id);
CREATE INDEX IF NOT EXISTS idx_resumes_slug   ON resumes(slug);

CREATE TABLE IF NOT EXISTS applications (
  id           TEXT        PRIMARY KEY,
  job_id       TEXT        NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  resume_id    TEXT        REFERENCES resumes(id) ON DELETE SET NULL,
  status       TEXT        NOT NULL DEFAULT 'planned',
  applied_at   TIMESTAMPTZ,
  last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  notes        TEXT,
  CHECK (status IN ('planned','draft','submitted','responded','interview','offer','rejected','withdrawn'))
);

CREATE INDEX IF NOT EXISTS idx_applications_job_id  ON applications(job_id);
CREATE INDEX IF NOT EXISTS idx_applications_status  ON applications(status);
