from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import psycopg

from pyapi.config import find_migrations_dir

logger = logging.getLogger("pyapi.migrations")

SCHEMA_MIGRATIONS_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
  version    TEXT        PRIMARY KEY,
  applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


@dataclass(frozen=True)
class Migration:
    version: str
    path: Path

    @property
    def sql(self) -> str:
        return self.path.read_text()


def discover_migrations(directory: Path | None = None) -> list[Migration]:
    root = directory or find_migrations_dir()
    files = sorted(root.glob("*.sql"))
    return [Migration(version=path.stem, path=path) for path in files]


def applied_versions(connection: psycopg.Connection) -> set[str]:
    with connection.cursor() as cur:
        cur.execute(SCHEMA_MIGRATIONS_SQL)
        cur.execute("SELECT version FROM schema_migrations")
        return {row[0] for row in cur.fetchall()}


def apply_migrations(database_url: str, directory: Path | None = None) -> list[str]:
    """Apply pending migrations against the Postgres URL. Returns versions applied this run."""
    migrations = discover_migrations(directory)
    applied_now: list[str] = []
    with psycopg.connect(database_url, autocommit=False) as connection:
        already = applied_versions(connection)
        connection.commit()
        for migration in migrations:
            if migration.version in already:
                continue
            logger.info("applying migration %s", migration.version)
            with connection.cursor() as cur:
                cur.execute(migration.sql)
                cur.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s)",
                    (migration.version,),
                )
            connection.commit()
            applied_now.append(migration.version)
    return applied_now


def main() -> None:
    import os
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

    from pyapi.config import load_dotenv_upwards

    load_dotenv_upwards()
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url.startswith("postgres"):
        print(f"DATABASE_URL must be a Postgres URL, got: {database_url!r}", file=sys.stderr)
        sys.exit(2)

    applied = apply_migrations(database_url)
    if applied:
        print("applied:", ", ".join(applied))
    else:
        print("nothing to apply — schema is up to date")


if __name__ == "__main__":
    main()
