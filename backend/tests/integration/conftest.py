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

# Package 01 fixtures (real LiteLLM container and fake provider).
from tests.integration.litellm_support import (  # noqa: F401
    catalog,
    clean_litellm,
    litellm_db,
    llm_settings,
)

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


# --- 03a: the real application against the throwaway database ---

CONSOLE_ORIGIN = "https://testserver"
PASSWORD = "dummy-not-secret-password-0123"


@pytest.fixture
def app_settings():
    from ffcore.core.config import Settings
    from tests.dummy import OBO_SECRET, SERVICE_TOKEN, SETTINGS_03A

    return Settings(
        deploy_profile=os.environ.get("DEPLOY_PROFILE", "llmaas"),
        offline=False,
        service_token=SERVICE_TOKEN,
        obo_jwt_secret=OBO_SECRET,
        console_origins=[CONSOLE_ORIGIN],
        **SETTINGS_03A,
    )


@pytest.fixture
def app(database_url, app_settings):
    from ffcore.core import db
    from ffcore.core.config import get_settings
    from ffcore.main import app

    db.configure(database_url, pooled=False)
    app.dependency_overrides[get_settings] = lambda: app_settings
    yield app
    app.dependency_overrides.clear()
    db.reset()


@pytest.fixture
def client_factory(app):
    """New TestClient per caller (each keeps its own cookie jar); https so Secure cookies flow."""
    from fastapi.testclient import TestClient

    clients = []

    def make(email: str | None = None, password: str = PASSWORD):
        client = TestClient(app, base_url=CONSOLE_ORIGIN)
        client.__enter__()
        clients.append(client)
        if email is not None:
            response = client.post(
                "/api/v1/auth/login", json={"email": email, "password": password}
            )
            assert response.status_code == 200, response.text
        return client

    yield make
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def make_user(pg):
    """Insert a user (argon2 hash) with optional memberships {project_id: (role, access)}."""
    from ffcore.core.passwords import hash_password

    hashed = hash_password(PASSWORD)

    def make(email=None, *, superadmin=None, active=True, memberships=None):
        user_id = uuid.uuid4()
        email = email or f"user-{user_id.hex[:8]}@example.test"
        pg.execute(
            "INSERT INTO users (id, email, password_hash, full_name, is_active, is_superadmin,"
            " superadmin_access) VALUES (%s, %s, %s, 'Test User', %s, %s, %s)",
            (user_id, email, hashed, active, superadmin is not None, superadmin),
        )
        for project_id, (role, access) in (memberships or {}).items():
            pg.execute(
                "INSERT INTO project_members (project_id, user_id, role, access, created_by)"
                " VALUES (%s, %s, %s, %s, 'test')",
                (project_id, user_id, role, access),
            )
        return user_id, email

    return make


@pytest.fixture
def make_project(pg):
    def make(key=None):
        project_id = uuid.uuid4()
        pg.execute(
            "INSERT INTO projects (id, key, name, created_by) VALUES (%s, %s, %s, 'test')",
            (project_id, key or f"p-{project_id.hex[:10]}", "Test project"),
        )
        return project_id

    return make


def audit_rows(pg, action, outcome=None):
    query = "SELECT actor_id, outcome, after FROM audit_events WHERE action = %s"
    params = [action]
    if outcome:
        query += " AND outcome = %s"
        params.append(outcome)
    return pg.execute(query + " ORDER BY ts", params).fetchall()
