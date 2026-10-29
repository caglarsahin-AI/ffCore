"""05a slice 5: mcp-sql end to end. Acceptance 1 (discover lists two actions), 2 (DELETE refused
before the database), 3 (row cut said), the read-only login, statement timeout, get_schema with
descriptions and the nearest few-shots (FAKE_EMBED), and the demo/context seed commands.

Chain: mcp_client -> mcp-sql (127.0.0.1) -> demo database (its own throwaway database here)
and, for get_schema, -> the real backend over HTTP (sql-context, on behalf of the caller).
"""

import asyncio
import uuid
from pathlib import Path

import psycopg
import pytest
from pydantic import SecretStr
from sqlalchemy.engine import make_url

from ffcore.core import db
from ffcore.services import mcp_client, mcp_sql_context, mcp_sql_demo, mcp_sql_server
from ffcore.services.mcp_client import Caller, ToolTarget
from tests.integration.test_05a_search import _serve

SCHEMA_DIR = Path(__file__).resolve().parents[3] / "data" / "samples" / "schema"
TOOL_KEY = "mcp-sql"
DEMO_PASSWORD = "agent_demo"


def _plain(url: str) -> str:
    return make_url(url).set(drivername="postgresql").render_as_string(hide_password=False)


@pytest.fixture(scope="module")
def demo(database_url):
    """A throwaway demo database and login user, made by the same code as `make seed-sql-demo`."""
    admin = _plain(database_url)
    name, user = f"agent_demo_{uuid.uuid4().hex[:8]}", f"mcp_sql_{uuid.uuid4().hex[:8]}"
    login = mcp_sql_demo.seed_demo(
        admin, database=name, login_user=user, password=DEMO_PASSWORD, schema_dir=SCHEMA_DIR
    )
    yield login
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        conn.execute(f'DROP ROLE IF EXISTS "{user}"')


@pytest.fixture
def settings(app, app_settings, demo):
    from ffcore.core.config import get_settings

    value = app_settings.model_copy(
        update={
            "fake_embed": True,
            "allowed_internal_hosts": [*app_settings.allowed_internal_hosts, "127.0.0.0/8"],
            "sql_demo_database_url": SecretStr(demo),
        }
    )
    app.dependency_overrides[get_settings] = lambda: value
    return value


@pytest.fixture
def world(make_user, make_project, client_factory, settings, database_url):
    project = make_project()
    admin_id, admin = make_user(memberships={project: ("admin", "edit")})
    user_id, _ = make_user(memberships={project: ("user", "edit")})

    async def load():
        db.configure(database_url, pooled=False)
        try:
            async with db.session_scope() as session:
                report = await mcp_sql_context.load(
                    session, project, SCHEMA_DIR, settings, created_by="test"
                )
                await session.commit()
                return report
        finally:
            db.reset()

    report = asyncio.run(load())
    db.configure(database_url, pooled=False)  # the app fixture's configuration, back again
    return {
        "project": str(project),
        "admin": client_factory(admin),
        "admin_id": str(admin_id),
        "user_id": str(user_id),
        "loaded": report,
    }


@pytest.fixture
def chain(app, settings):
    backend_host, backend = _serve(app)
    sql_settings = settings.model_copy(update={"internal_api_url": f"http://{backend_host}"})
    host, server = _serve(
        mcp_sql_server.build_app(sql_settings, tool_key=TOOL_KEY, allowed_hosts=["127.0.0.1:*"])
    )
    yield f"http://{host}/mcp", sql_settings
    server.should_exit = backend.should_exit = True


def _call(chain, settings, world, action, arguments):
    url, _ = chain
    target = ToolTarget(key=TOOL_KEY, endpoint_url=url, auth_type="forward_user", auth={})
    return asyncio.run(
        mcp_client.call(
            target, action, arguments, settings, caller=Caller(world["user_id"], world["project"])
        )
    )


def test_05a_seed_context_report(world):
    assert world["loaded"] == (46, 20)


def test_05a_1_discover_mcp_sql_lists_two_actions(chain, settings, world):
    url, _ = chain
    tools = f"/api/v1/projects/{world['project']}/tools"
    body = {
        "key": TOOL_KEY,
        "name": "SQL",
        "kind": "mcp",
        "endpoint_url": url,
        "auth": {"type": "forward_user"},
    }
    tool = world["admin"].post(tools, json=body).json()
    found = world["admin"].post(f"{tools}/{tool['id']}/discover").json()
    assert found["status"] == "discovered", found
    actions = {a["name"]: a for a in found["actions"]}
    assert set(actions) == {"get_schema", "run_sql"}
    # C7: get_schema(question?), run_sql(sql, reason).
    assert "question" not in actions["get_schema"]["input_schema"].get("required", [])
    assert set(actions["run_sql"]["input_schema"]["required"]) == {"sql", "reason"}


def test_05a_2_delete_rejected_before_db(chain, settings, world, demo):
    before = psycopg.connect(demo).execute("SELECT count(*) FROM departments").fetchone()[0]
    result = _call(
        chain, settings, world, "run_sql", {"sql": "DELETE FROM departments", "reason": "t"}
    )
    assert result.text.startswith("sql_rejected: sql_not_select"), result.text
    after = psycopg.connect(demo).execute("SELECT count(*) FROM departments").fetchone()[0]
    assert before == after > 0


def test_05a_3_run_sql_truncates_rows_marked(chain, settings, world):
    result = _call(
        chain, settings, world, "run_sql", {"sql": "SELECT * FROM admissions", "reason": "t"}
    )
    lines = result.text.splitlines()
    assert lines[-2] == "rows: 500"
    assert lines[-1] == "[truncated: first 500 rows shown; the query returned more]"
    assert len(lines) == 1 + 500 + 2  # header, rows, count, marker


def test_05a_run_sql_returns_rows(chain, settings, world):
    sql = "SELECT code, bed_capacity FROM departments ORDER BY id LIMIT 2"
    result = _call(chain, settings, world, "run_sql", {"sql": sql, "reason": "t"})
    lines = result.text.splitlines()
    assert lines[0] == "code,bed_capacity" and lines[-1] == "rows: 2" and len(lines) == 4


def test_05a_run_sql_unknown_table_and_db_error_coded(chain, settings, world):
    unknown = _call(
        chain, settings, world, "run_sql", {"sql": "SELECT * FROM patients", "reason": "t"}
    )
    assert unknown.text.startswith("sql_rejected: sql_unknown_table")
    bad = _call(chain, settings, world, "run_sql", {"sql": "SELECT nope FROM beds", "reason": "t"})
    assert bad.text.startswith("sql_error: 42703")


def test_05a_run_sql_timeout(chain, settings, world):
    _, sql_settings = chain
    sql_settings.sql_timeout_s = 1
    heavy = "SELECT count(*) FROM admissions a, admissions b, admissions c"
    result = _call(chain, settings, world, "run_sql", {"sql": heavy, "reason": "t"})
    assert result.text.startswith("sql_error: sql_timeout"), result.text


def test_05a_demo_login_is_read_only(demo):
    with psycopg.connect(demo) as conn, pytest.raises(psycopg.Error):
        conn.execute(
            "INSERT INTO departments (id, code, name_tr, floor, bed_capacity)"
            " VALUES (999, 'X', 'X', 1, 1)"
        )


def test_05a_seed_demo_is_idempotent(database_url, demo):
    url = make_url(demo)
    again = mcp_sql_demo.seed_demo(
        _plain(database_url),
        database=url.database,
        login_user=url.username,
        password=DEMO_PASSWORD,
        schema_dir=SCHEMA_DIR,
    )
    assert make_url(again).database == url.database


def test_05a_get_schema_narrows_and_adds_examples(chain, settings, world):
    result = _call(chain, settings, world, "get_schema", {"question": "yatak kapasitesi"})
    assert not result.is_error, result.text
    assert "departments" in result.text and "bed_capacity" in result.text
    assert "contracts_meta" not in result.text
    assert result.text.count("SQL: ") == 5
    everything = _call(chain, settings, world, "get_schema", {})
    assert all(t in everything.text for t in ("departments", "contracts_meta", "device_faults"))


def test_05a_sql_context_roles(world, client_factory, make_user, make_project):
    other = make_project()
    _, stranger = make_user(memberships={other: ("admin", "edit")})
    url = f"/api/v1/projects/{world['project']}/tools/sql-context"
    assert client_factory(stranger).post(url, json={}).status_code == 403
    assert world["admin"].post(url, json={"question": "yatak"}).status_code == 200


def test_05a_cli_seed_sql_context(database_url, make_project, settings, monkeypatch):
    from ffcore import cli

    project = make_project(key="sqlseed-" + uuid.uuid4().hex[:6])
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    db.configure(database_url, pooled=False)
    try:
        key = (
            psycopg.connect(_plain(database_url))
            .execute("SELECT key FROM projects WHERE id = %s", (project,))
            .fetchone()[0]
        )
        first = asyncio.run(cli._seed_sql_context(key, SCHEMA_DIR))
        second = asyncio.run(cli._seed_sql_context(key, SCHEMA_DIR))  # a reload replaces
    finally:
        db.reset()
    assert first == second == (46, 20)
    rows = (
        psycopg.connect(_plain(database_url))
        .execute(
            "SELECT count(*) FROM schema_descriptions WHERE project_id = %s AND deleted_at IS NULL",
            (project,),
        )
        .fetchone()[0]
    )
    assert rows == 46


def test_05a_cli_seed_sql_demo_needs_password(settings):
    from ffcore import cli

    with pytest.raises(cli.CliError, match="AGENT_DEMO_DB_PASSWORD"):
        cli._seed_sql_demo(settings.model_copy(update={"agent_demo_db_password": None}), SCHEMA_DIR)


@pytest.mark.models  # real bge-m3 weights (RUN_MODEL_TESTS=1, `make models`)
def test_05a_models_few_shot_similarity(database_url, make_project, settings):
    real = settings.model_copy(update={"fake_embed": False})
    project = make_project()

    async def go():
        db.configure(database_url, pooled=False)
        try:
            async with db.session_scope() as session:
                await mcp_sql_context.load(session, project, SCHEMA_DIR, real, created_by="test")
                found = await mcp_sql_context.context(
                    session, project, "Kardiyolojide kaç yatak var?", real
                )
                await session.rollback()
                return found
        finally:
            db.reset()

    found = asyncio.run(go())
    assert "KARD" in found.examples[0][1] and "bed_capacity" in found.examples[0][1]
