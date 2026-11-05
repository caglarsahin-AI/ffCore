"""05a slice 5: mcp-sql end to end. Acceptance 1 (discover lists two actions), 2 (DELETE refused
before the database), 3 (row cut said), the read-only login, statement timeout, get_schema with
descriptions and the nearest few-shots (FAKE_EMBED), and the demo/context seed commands.

Chain: mcp_client -> mcp-sql (127.0.0.1) -> demo database (its own throwaway database here)
and, for get_schema, -> the real backend over HTTP (sql-context, on behalf of the caller).
"""

import asyncio
import time
import uuid
from pathlib import Path

import psycopg
import pytest
from pydantic import SecretStr
from sqlalchemy.engine import make_url

from ffcore.core import db
from ffcore.services import mcp_client, mcp_sql_context, mcp_sql_demo, mcp_sql_server
from ffcore.services.mcp_client import Caller, ToolCallError, ToolTarget
from tests.integration.test_05a_search import _serve
from tests.sql_matrix import REJECTED

SCHEMA_DIR = Path(__file__).resolve().parents[3] / "data" / "samples" / "schema"
TOOL_KEY = "mcp-sql"
DEMO_PASSWORD = "agent_demo"
SQL_TOOL = "http://mcp-sql:8000/mcp"


def _register_tool(pg, settings, project, key=TOOL_KEY) -> uuid.UUID:
    """A registered mcp-sql tool row: the parent of the project's SQL examples (C3)."""
    from ffcore.services.mcp_tools import encrypt_auth

    tool_id = uuid.uuid4()
    pg.execute(
        "INSERT INTO tools (id, project_id, key, name, kind, endpoint_url, auth_type,"
        " auth_config_encrypted, created_by) VALUES (%s, %s, %s, 'SQL', 'mcp', %s,"
        " 'forward_user', %s, 'test')",
        (tool_id, project, key, SQL_TOOL, encrypt_auth({}, settings)),
    )
    return tool_id


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
def world(make_user, make_project, client_factory, settings, database_url, pg):
    project = make_project()
    admin_id, admin = make_user(memberships={project: ("admin", "edit")})
    user_id, _ = make_user(memberships={project: ("user", "edit")})
    tool_id = _register_tool(pg, settings, project)

    async def load():
        db.configure(database_url, pooled=False)
        try:
            async with db.session_scope() as session:
                report = await mcp_sql_context.load(
                    session, tool_id, SCHEMA_DIR, settings, created_by="test"
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
        "tool_id": str(tool_id),
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
    # The world's registered mcp-sql tool, pointed at this test's server.
    moved = world["admin"].patch(f"{tools}/{world['tool_id']}", json={"endpoint_url": url})
    assert moved.status_code == 200, moved.text
    found = world["admin"].post(f"{tools}/{world['tool_id']}/discover").json()
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


def test_05a_run_sql_refusal_and_db_error_are_tool_errors(chain, settings, world):
    """09-1 r2 MAJOR-r2-3 (KARARLAR "09-1 r2 kararları", 05a additive): a refused query and a
    database error come back as a tool error with the same coded text; rows do not."""
    unknown = _call(
        chain, settings, world, "run_sql", {"sql": "SELECT * FROM patients", "reason": "t"}
    )
    assert unknown.is_error and unknown.text.startswith("sql_rejected: sql_unknown_table")
    bad = _call(chain, settings, world, "run_sql", {"sql": "SELECT nope FROM beds", "reason": "t"})
    assert bad.is_error and bad.text.startswith("sql_error: 42703")
    rows = _call(chain, settings, world, "run_sql", {"sql": "SELECT 1 AS n", "reason": "t"})
    assert not rows.is_error, rows.text


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
    body = {"tool_key": TOOL_KEY}
    assert client_factory(stranger).post(url, json=body).status_code == 404
    assert world["admin"].post(url, json={**body, "question": "yatak"}).status_code == 200


def test_05a_cli_seed_sql_context(database_url, make_project, settings, monkeypatch, pg):
    from ffcore import cli

    project = make_project(key="sqlseed-" + uuid.uuid4().hex[:6])
    tool_id = _register_tool(pg, settings, project)
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    db.configure(database_url, pooled=False)
    try:
        key = (
            psycopg.connect(_plain(database_url))
            .execute("SELECT key FROM projects WHERE id = %s", (project,))
            .fetchone()[0]
        )
        first = asyncio.run(cli._seed_sql_context(key, TOOL_KEY, SCHEMA_DIR))
        second = asyncio.run(cli._seed_sql_context(key, TOOL_KEY, SCHEMA_DIR))  # replaces
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
    shots = pg.execute("SELECT count(*) FROM few_shots WHERE tool_id = %s", (tool_id,)).fetchone()
    assert shots[0] == 20


def test_05a_cli_seed_sql_context_needs_the_tool(database_url, make_project, settings, monkeypatch):
    from ffcore import cli

    project = make_project(key="sqlnotool-" + uuid.uuid4().hex[:6])
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    db.configure(database_url, pooled=False)
    try:
        key = (
            psycopg.connect(_plain(database_url))
            .execute("SELECT key FROM projects WHERE id = %s", (project,))
            .fetchone()[0]
        )
        with pytest.raises(cli.CliError, match="register"):
            asyncio.run(cli._seed_sql_context(key, TOOL_KEY, SCHEMA_DIR))
    finally:
        db.reset()


def test_05a_cli_seed_sql_demo_needs_password(settings):
    from ffcore import cli

    with pytest.raises(cli.CliError, match="AGENT_DEMO_DB_PASSWORD"):
        cli._seed_sql_demo(settings.model_copy(update={"agent_demo_db_password": None}), SCHEMA_DIR)


@pytest.mark.models  # real bge-m3 weights (RUN_MODEL_TESTS=1, `make models`)
def test_05a_models_few_shot_similarity(database_url, make_project, settings, pg):
    real = settings.model_copy(update={"fake_embed": False})
    project = make_project()
    tool_id = _register_tool(pg, settings, project)

    async def go():
        db.configure(database_url, pooled=False)
        try:
            async with db.session_scope() as session:
                await mcp_sql_context.load(session, tool_id, SCHEMA_DIR, real, created_by="test")
                found = await mcp_sql_context.context(
                    session, tool_id, "Kardiyolojide kaç yatak var?", real
                )
                await session.rollback()
                return found
        finally:
            db.reset()

    found = asyncio.run(go())
    assert "KARD" in found.examples[0][1] and "bed_capacity" in found.examples[0][1]


# --- review r1 BLOCKER-1: few_shots is a child of the registered mcp-sql tool (C3) ---


def test_05a_few_shots_is_a_child_of_tools_in_the_database(pg):
    columns = dict(
        pg.execute(
            "SELECT column_name, is_nullable FROM information_schema.columns"
            " WHERE table_name = 'few_shots'"
        ).fetchall()
    )
    assert "project_id" not in columns
    assert columns["tool_id"] == "NO"
    targets = pg.execute(
        "SELECT ccu.table_name, ccu.column_name FROM information_schema.table_constraints tc"
        " JOIN information_schema.constraint_column_usage ccu"
        " ON ccu.constraint_name = tc.constraint_name"
        " WHERE tc.table_name = 'few_shots' AND tc.constraint_type = 'FOREIGN KEY'"
    ).fetchall()
    assert targets == [("tools", "id")]


def test_05a_sql_context_examples_follow_the_tool(world, pg, settings):
    # A second SQL tool in the same project, without examples: examples belong to one tool.
    _register_tool(pg, settings, uuid.UUID(world["project"]), key="mcp-sql-2")
    url = f"/api/v1/projects/{world['project']}/tools/sql-context"
    question = {"question": "yatak kapasitesi"}
    own = world["admin"].post(url, json={**question, "tool_key": TOOL_KEY})
    other = world["admin"].post(url, json={**question, "tool_key": "mcp-sql-2"})
    assert own.status_code == 200 and len(own.json()["examples"]) == 5
    assert other.status_code == 200 and other.json()["examples"] == []
    missing = world["admin"].post(url, json={**question, "tool_key": "no-such-tool"})
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "tool_not_found"
    tools = f"/api/v1/projects/{world['project']}/tools"
    assert world["admin"].delete(f"{tools}/{world['tool_id']}").status_code == 204
    gone = world["admin"].post(url, json={**question, "tool_key": TOOL_KEY})
    assert gone.status_code == 404


# --- review r1 MAJOR-1 and MINOR-1: nothing refused reaches the demo database. The proof is
# the database's own counter of sessions (pg_stat_database.sessions, counted when a session
# ends), checked against one control query that does open a session.

FORGED_KEY = "dummy-not-secret-forged-obo-key-0123456789abcdef"


def _demo_sessions(database_url, demo) -> int:
    with psycopg.connect(_plain(database_url), autocommit=True) as conn:
        row = conn.execute(
            "SELECT sessions FROM pg_stat_database WHERE datname = %s",
            (make_url(demo).database,),
        ).fetchone()
    return row[0]


def _settled(database_url, demo) -> int:
    """The counter once sessions of earlier tests have been counted."""
    last = _demo_sessions(database_url, demo)
    while True:
        time.sleep(1.5)
        now = _demo_sessions(database_url, demo)
        if now == last:
            return now
        last = now


def _after_one_control_query(chain, settings, world, database_url, demo, before) -> int:
    control = {"sql": "SELECT id FROM beds LIMIT 1", "reason": "control"}
    result = _call(chain, settings, world, "run_sql", control)
    assert result.text.endswith("rows: 1"), result.text
    deadline = time.monotonic() + 10
    while _demo_sessions(database_url, demo) < before + 1:
        assert time.monotonic() < deadline, "the control session was never counted"
        time.sleep(0.2)
    return _settled(database_url, demo)


def test_05a_sql_matrix_never_reaches_the_database(chain, settings, world, database_url, demo):
    before = _settled(database_url, demo)
    for sql, code in REJECTED:
        result = _call(chain, settings, world, "run_sql", {"sql": sql, "reason": "matrix"})
        assert result.text.startswith(f"sql_rejected: {code} "), (sql, result.text)
    assert _after_one_control_query(chain, settings, world, database_url, demo, before) == (
        before + 1
    )


def test_05a_forged_token_refused_before_the_database(
    chain, settings, world, database_url, demo, make_project
):
    """Review r1 MAJOR-1: signed with the wrong key, listing mcp-sql, for another user and
    project. The routing read lets it through; the backend's verification refuses it."""
    url, _ = chain
    forger = settings.model_copy(update={"obo_jwt_secret": SecretStr(FORGED_KEY)})
    target = ToolTarget(key=TOOL_KEY, endpoint_url=url, auth_type="forward_user", auth={})
    fake = Caller(user_id=str(uuid.uuid4()), project_id=str(make_project()))
    before = _settled(database_url, demo)
    for action, arguments in (
        ("run_sql", {"sql": "SELECT id FROM beds", "reason": "forged"}),
        ("get_schema", {}),
    ):
        with pytest.raises(ToolCallError) as err:
            asyncio.run(mcp_client.call(target, action, arguments, forger, caller=fake))
        assert err.value.code == "tool_auth_failed"
    assert _after_one_control_query(chain, settings, world, database_url, demo, before) == (
        before + 1
    )


def test_05a_forged_token_answer_is_coded(chain, settings, world):
    import httpx2

    from ffcore.core.auth import sign_on_behalf_of
    from tests.dummy import SERVICE_TOKEN

    url, _ = chain
    forger = settings.model_copy(update={"obo_jwt_secret": SecretStr(FORGED_KEY)})
    token = sign_on_behalf_of(
        user_id=world["user_id"],
        project_id=world["project"],
        audience=[TOOL_KEY, settings.obo_audience],
        settings=forger,
        ttl_s=60,
    )
    response = httpx2.post(
        url,
        headers={"Authorization": f"Bearer {SERVICE_TOKEN}", "X-On-Behalf-Of": token},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"
