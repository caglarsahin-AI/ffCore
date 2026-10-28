"""Integration fixtures: a throwaway database on the compose Postgres, migrated with Alembic.

Run in the tools container: docker compose run --rm tools make test-int (postgres must be up).
"""

import os
import subprocess
import uuid
from pathlib import Path

import psycopg
import pytest
from sqlalchemy.engine import make_url

BACKEND = Path(__file__).resolve().parents[2]
ALLOWED_DB_HOSTS = {"postgres", "localhost", "127.0.0.1"}


def _admin_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.fail("DATABASE_URL is not set; run integration tests in the tools container")
    parsed = make_url(url)
    if parsed.host not in ALLOWED_DB_HOSTS:
        pytest.fail(f"refusing to run integration tests against host {parsed.host!r}")
    return url


@pytest.fixture(scope="session")
def database_url() -> str:
    admin = make_url(_admin_url())
    name = f"ffcore_test_{uuid.uuid4().hex[:12]}"
    plain = admin.set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg.connect(plain, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')
    url = admin.set(database=name).render_as_string(hide_password=False)
    try:
        subprocess.run(
            ["alembic", "upgrade", "heads"],
            cwd=BACKEND,
            env={**os.environ, "DATABASE_URL": url},
            check=True,
            capture_output=True,
        )
        yield url
    finally:
        with psycopg.connect(plain, autocommit=True) as conn:
            conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


@pytest.fixture
def pg(database_url):
    plain = make_url(database_url).set(drivername="postgresql")
    with psycopg.connect(plain.render_as_string(hide_password=False), autocommit=True) as conn:
        yield conn
