"""CRUD tools for the jobs / applications / resumes tables.

Each tool is a thin wrapper around a SQL statement against the Postgres URL the
ToolConfig already carries. Connections are opened per-call (psycopg autocommit) —
the call volume from the LLM is too low to justify a pool.

Tools exposed:
    store_job          {portal, url, title, company?, location?, salary_min?, salary_max?, salary_currency?, external_id?, raw_meta?}
                          → {id, ok}
    store_jd           {raw_text, job_id?, source_url?, parsed?}  → {id, ok}
    log_application    {job_id, resume_id?, status?, notes?}      → {id, ok}
    update_status      {id, status, notes?}                       → {id, ok}
    list_applications  {status?, limit?}                          → {applications:[…], count}
"""

from __future__ import annotations

import json
import logging
import secrets
from typing import Any

import psycopg

from pyapi.config import ToolConfig

from .args import string_arg

logger = logging.getLogger("pyapi.tools.applications")

VALID_STATUSES: tuple[str, ...] = (
    "planned", "draft", "submitted", "responded", "interview", "offer", "rejected", "withdrawn",
)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(12)}"


def _connect(config: ToolConfig) -> psycopg.Connection:
    return psycopg.connect(config.database_url, autocommit=True)


def run_store_job(config: ToolConfig, arguments: dict[str, Any], _sid: str | None = None) -> str:
    portal = string_arg(arguments, "portal", "").strip().lower()
    url = string_arg(arguments, "url", "").strip()
    title = string_arg(arguments, "title", "").strip()
    if not portal or not url or not title:
        raise ValueError("portal, url, and title are required")

    job_id = _new_id("job")
    external_id = string_arg(arguments, "external_id", "").strip() or None
    with _connect(config) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO jobs (id, portal, external_id, url, title, company, location,
                              salary_min, salary_max, salary_currency, raw_meta)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (portal, external_id) DO UPDATE
              SET url = EXCLUDED.url, title = EXCLUDED.title,
                  company = EXCLUDED.company, location = EXCLUDED.location
            RETURNING id
            """,
            (
                job_id,
                portal,
                external_id,
                url,
                title,
                string_arg(arguments, "company", "").strip() or None,
                string_arg(arguments, "location", "").strip() or None,
                arguments.get("salary_min"),
                arguments.get("salary_max"),
                string_arg(arguments, "salary_currency", "").strip() or None,
                json.dumps(arguments.get("raw_meta") or {}),
            ),
        )
        actual_id = cur.fetchone()[0]
    return json.dumps({"ok": True, "id": actual_id}, indent=2)


def run_store_jd(config: ToolConfig, arguments: dict[str, Any], _sid: str | None = None) -> str:
    raw_text = string_arg(arguments, "raw_text", "").strip()
    if not raw_text:
        raise ValueError("raw_text is required")
    jd_id = _new_id("jd")
    parsed = arguments.get("parsed") or {}
    with _connect(config) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO jds (id, job_id, source_url, raw_text, parsed)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            RETURNING id
            """,
            (
                jd_id,
                string_arg(arguments, "job_id", "").strip() or None,
                string_arg(arguments, "source_url", "").strip() or None,
                raw_text,
                json.dumps(parsed),
            ),
        )
        actual_id = cur.fetchone()[0]
    return json.dumps({"ok": True, "id": actual_id}, indent=2)


def run_log_application(config: ToolConfig, arguments: dict[str, Any], _sid: str | None = None) -> str:
    job_id = string_arg(arguments, "job_id", "").strip()
    if not job_id:
        raise ValueError("job_id is required")
    status = string_arg(arguments, "status", "planned").strip().lower()
    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of: {', '.join(VALID_STATUSES)}")
    app_id = _new_id("app")
    with _connect(config) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO applications (id, job_id, resume_id, status, notes)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                app_id,
                job_id,
                string_arg(arguments, "resume_id", "").strip() or None,
                status,
                string_arg(arguments, "notes", "").strip() or None,
            ),
        )
        actual_id = cur.fetchone()[0]
    return json.dumps({"ok": True, "id": actual_id}, indent=2)


def run_update_status(config: ToolConfig, arguments: dict[str, Any], _sid: str | None = None) -> str:
    app_id = string_arg(arguments, "id", "").strip()
    status = string_arg(arguments, "status", "").strip().lower()
    if not app_id or not status:
        raise ValueError("id and status are required")
    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of: {', '.join(VALID_STATUSES)}")
    notes = string_arg(arguments, "notes", "").strip() or None
    with _connect(config) as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE applications
               SET status = %s,
                   notes = COALESCE(%s, notes),
                   last_updated = NOW(),
                   applied_at = CASE
                       WHEN %s = 'submitted' AND applied_at IS NULL THEN NOW()
                       ELSE applied_at
                   END
             WHERE id = %s
            RETURNING id
            """,
            (status, notes, status, app_id),
        )
        row = cur.fetchone()
    if not row:
        raise ValueError(f"application {app_id} not found")
    return json.dumps({"ok": True, "id": row[0]}, indent=2)


def run_list_applications(config: ToolConfig, arguments: dict[str, Any], _sid: str | None = None) -> str:
    status = string_arg(arguments, "status", "").strip().lower() or None
    limit = max(1, min(100, int(arguments.get("limit") or 25)))
    with _connect(config) as conn, conn.cursor() as cur:
        if status:
            cur.execute(
                """
                SELECT a.id, a.status, a.applied_at, a.last_updated, a.notes,
                       j.title, j.company, j.location, j.url
                  FROM applications a
                  JOIN jobs j ON j.id = a.job_id
                 WHERE a.status = %s
                 ORDER BY a.last_updated DESC
                 LIMIT %s
                """,
                (status, limit),
            )
        else:
            cur.execute(
                """
                SELECT a.id, a.status, a.applied_at, a.last_updated, a.notes,
                       j.title, j.company, j.location, j.url
                  FROM applications a
                  JOIN jobs j ON j.id = a.job_id
                 ORDER BY a.last_updated DESC
                 LIMIT %s
                """,
                (limit,),
            )
        rows = cur.fetchall()

    applications = [
        {
            "id": r[0],
            "status": r[1],
            "applied_at": r[2].isoformat() if r[2] else None,
            "last_updated": r[3].isoformat() if r[3] else None,
            "notes": r[4],
            "title": r[5],
            "company": r[6],
            "location": r[7],
            "url": r[8],
        }
        for r in rows
    ]
    return json.dumps({"count": len(applications), "applications": applications}, indent=2, ensure_ascii=False)
