"""The demo database mcp-sql queries (13a's synthetic agent presentation DB; K-05a-0002 S5).

`make seed-sql-demo` (cli seed-sql-demo) creates it in the existing Postgres: its own database,
13a's schema.sql and seed.sql, the agent_readonly role (13a readonly_role.sql) and a login user
in that role whose password comes from AGENT_DEMO_DB_PASSWORD (.env, written by the user).
Idempotent: an existing database keeps its data; the role and the login user are set again.

Role-level settings do not pass to role members in Postgres, so the login user gets
default_transaction_read_only and statement_timeout itself as well.
"""

from pathlib import Path

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

READONLY_ROLE = "agent_readonly"


def _statements(script: str) -> list[str]:
    """13a's readonly_role.sql: one statement per line, comments dropped."""
    lines = [ln.strip() for ln in script.splitlines() if ln.strip() and not ln.startswith("--")]
    return [ln.rstrip(";") for ln in lines]


def seed_demo(
    admin_url: str,
    *,
    database: str,
    login_user: str,
    password: str,
    schema_dir: Path,
    statement_timeout_s: int = 20,
) -> str:
    """Returns the login user's URL for the demo database (SQL_DEMO_DATABASE_URL)."""
    if not password:
        raise ValueError("AGENT_DEMO_DB_PASSWORD is not set")
    with psycopg.connect(admin_url, autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database,))
        if exists.fetchone() is None:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    demo_admin = make_url(admin_url).set(database=database).render_as_string(hide_password=False)
    with psycopg.connect(demo_admin, autocommit=True) as conn:
        tables = conn.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'"
        ).fetchone()[0]
        if tables == 0:
            conn.execute((schema_dir / "schema.sql").read_text(encoding="utf-8"))
            conn.execute((schema_dir / "seed.sql").read_text(encoding="utf-8"))
        role = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (READONLY_ROLE,))
        role_exists = role.fetchone() is not None
        for statement in _statements((schema_dir / "readonly_role.sql").read_text("utf-8")):
            if statement.upper().startswith("CREATE ROLE") and role_exists:
                continue
            conn.execute(statement)
        conn.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
        user = sql.Identifier(login_user)
        login = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (login_user,))
        verb = "ALTER" if login.fetchone() is not None else "CREATE"
        conn.execute(
            sql.SQL(verb + " ROLE {} WITH LOGIN PASSWORD {}").format(user, sql.Literal(password))
        )
        conn.execute(sql.SQL("GRANT {} TO {}").format(sql.Identifier(READONLY_ROLE), user))
        conn.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(database), user)
        )
        conn.execute(sql.SQL("ALTER ROLE {} SET default_transaction_read_only = on").format(user))
        conn.execute(
            sql.SQL("ALTER ROLE {} SET statement_timeout = {}").format(
                user, sql.Literal(f"{int(statement_timeout_s)}s")
            )
        )
    url = make_url(admin_url).set(database=database, username=login_user, password=password)
    return url.render_as_string(hide_password=False)
