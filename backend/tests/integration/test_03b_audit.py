import json
from datetime import UTC, datetime, timedelta
from typing import Annotated

import psycopg
import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import Column, MetaData, String, Table
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import registry

from ffcore.core import db
from ffcore.core.audit import audited, ensure_audit_partitions
from ffcore.core.auth import Actor, resolve_actor, sign_on_behalf_of
from ffcore.core.config import Settings, get_settings
from ffcore.core.errors import ApiError, install_error_handlers
from tests.dummy import SETTINGS_03A

PROJECT = "1f2e3d4c-5b6a-4978-8695-a4b3c2d1e0f9"
USER = "6d0e2f47-6f6a-4d2b-9a3e-1c2b3d4e5f60"
SETTINGS = Settings(
    deploy_profile="llmaas",
    offline=False,
    service_token="dummy-not-secret-service-token-0123456789",
    obo_jwt_secret="dummy-not-secret-obo-jwt-secret-0123456789",
    **SETTINGS_03A,
)


@pytest.fixture(autouse=True)
def configured_db(database_url):
    db.configure(database_url, pooled=False)
    yield
    db.reset()


def _rows(pg, action):
    return pg.execute(
        "SELECT actor_type, actor_id, project_id::text, resource_id, outcome, before, after,"
        " request_id, ip::text FROM audit_events WHERE action = %s ORDER BY ts",
        (action,),
    ).fetchall()


def _insert(pg, ts="now()"):
    pg.execute(
        "INSERT INTO audit_events (id, ts, actor_type, actor_id, action, resource_type, outcome)"
        f" VALUES (gen_random_uuid(), {ts}, 'system', 'test', 'probe', 'probe', 'success')"
    )


async def user_actor() -> Actor:
    return Actor(actor_type="user", actor_id=USER, project_id=PROJECT)


def _app() -> TestClient:
    app = FastAPI()
    install_error_handlers(app)
    app.dependency_overrides[get_settings] = lambda: SETTINGS

    async def load_thing(**_):
        return {"id": "t-1", "title": "old", "secret_note": "dummy-not-secret-before"}

    @app.post("/things")
    @audited("thing.update", "thing", redact_fields=["note"], load_before=load_thing)
    async def update(
        request: Request,
        actor: Annotated[Actor, Depends(user_actor)],
        session: Annotated[AsyncSession, Depends(db.get_session)],
    ):
        return {
            "id": "t-1",
            "title": "new",
            "note": "free text",
            "api_key": "dummy-not-secret-key",
            "nested": {
                "Password": "dummy-not-secret-pw",
                "items": [{"token": "dummy-not-secret-t"}],
            },
        }

    @app.post("/memories")
    @audited("memory.create", "memory", audit_payload=False)
    async def memory(
        request: Request,
        actor: Annotated[Actor, Depends(user_actor)],
        session: Annotated[AsyncSession, Depends(db.get_session)],
    ):
        return {"id": "m-1", "text": "the user's private memory"}

    @app.post("/forbidden")
    @audited("thing.delete", "thing")
    async def forbidden(
        request: Request,
        actor: Annotated[Actor, Depends(user_actor)],
        session: Annotated[AsyncSession, Depends(db.get_session)],
    ):
        await session.execute(
            db.text(
                "INSERT INTO audit_events (id, ts, actor_type, actor_id, action, resource_type,"
                " outcome) VALUES (gen_random_uuid(), now(), 'system', 'x', 'rolled.back', 'x',"
                " 'success')"
            )
        )
        raise ApiError(403, "permission_error", "read_only", "Read-only access.")

    @app.post("/broken")
    @audited("thing.break", "thing")
    async def broken(
        request: Request,
        actor: Annotated[Actor, Depends(user_actor)],
        session: Annotated[AsyncSession, Depends(db.get_session)],
    ):
        raise RuntimeError("boom")

    @app.post("/obo-things")
    @audited("thing.obo", "thing")
    async def obo_thing(
        request: Request,
        actor: Annotated[Actor, Depends(resolve_actor)],
        session: Annotated[AsyncSession, Depends(db.get_session)],
    ):
        return {"id": "t-2"}

    @app.get("/whoami")
    async def whoami(actor: Annotated[Actor, Depends(resolve_actor)]):
        return {"id": actor.actor_id}

    return TestClient(app, raise_server_exceptions=False)


# --- criterion 4: append-only ---------------------------------------------------------------


def test_03b_4_audit_delete_rejected(pg):
    _insert(pg)
    partition = pg.execute(
        "SELECT tableoid::regclass::text FROM audit_events WHERE action = 'probe' LIMIT 1"
    ).fetchone()[0]
    for statement in (
        "DELETE FROM audit_events WHERE action = 'probe'",
        f"DELETE FROM {partition} WHERE action = 'probe'",
        "UPDATE audit_events SET outcome = 'error' WHERE action = 'probe'",
        f"UPDATE {partition} SET outcome = 'error' WHERE action = 'probe'",
        "TRUNCATE audit_events",
        f"TRUNCATE {partition}",
    ):
        with pytest.raises(psycopg.Error, match="append-only"):
            pg.execute(statement)
    assert pg.execute("SELECT count(*) FROM audit_events WHERE action = 'probe'").fetchone()[0] >= 1


# --- criterion 6: monthly partitions --------------------------------------------------------


def test_03b_6_partition_helper_idempotent(pg, database_url):
    import anyio

    first = anyio.run(ensure_audit_partitions, 3)
    again = anyio.run(ensure_audit_partitions, 3)
    assert first == again and len(first) == 3
    today = datetime.now(UTC)
    assert first[0] == f"audit_events_{today:%Y_%m}"
    names = {
        row[0]
        for row in pg.execute(
            "SELECT inhrelid::regclass::text FROM pg_inherits"
            " WHERE inhparent = 'audit_events'::regclass"
        )
    }
    assert set(first) <= names


def test_03b_6_insert_without_partition_fails_loud(pg):
    far = (datetime.now(UTC) + timedelta(days=800)).strftime("%Y-%m-%d")
    with pytest.raises(psycopg.Error, match="no partition"):
        _insert(pg, ts=f"'{far}'::timestamptz")


# --- criterion 5: @audited ------------------------------------------------------------------


def test_03b_5_audited_writes_one_event_with_masking(pg):
    client = _app()
    response = client.post("/things", headers={"X-Request-ID": "req-03b-5"})
    assert response.status_code == 200
    rows = _rows(pg, "thing.update")
    assert len(rows) == 1
    actor_type, actor_id, project_id, resource_id, outcome, before, after, request_id, ip = rows[0]
    assert (actor_type, actor_id, project_id) == ("user", USER, PROJECT)
    assert (resource_id, outcome, request_id) == ("t-1", "success", "req-03b-5")
    assert ip == "testclient" or ip is None or ip.count(".") == 3
    assert before == {"id": "t-1", "title": "old", "secret_note": "***"}
    assert after["title"] == "new" and after["note"] == "***" and after["api_key"] == "***"
    assert after["nested"] == {"Password": "***", "items": [{"token": "***"}]}
    assert "dummy-not-secret" not in json.dumps([before, after])


def test_03b_5_payload_false_no_content(pg):
    assert _app().post("/memories").status_code == 200
    rows = _rows(pg, "memory.create")
    assert len(rows) == 1
    assert rows[0][3] == "m-1" and rows[0][5] is None and rows[0][6] is None


def test_03b_5_denied_outcome_survives_rollback(pg):
    response = _app().post("/forbidden")
    assert response.status_code == 403
    rows = _rows(pg, "thing.delete")
    assert [row[4] for row in rows] == ["denied"]
    # The endpoint's own write was rolled back; the denial was recorded on its own.
    assert _rows(pg, "rolled.back") == []


def test_03b_5_error_outcome_recorded(pg):
    response = _app().post("/broken")
    assert response.status_code == 500
    assert [row[4] for row in _rows(pg, "thing.break")] == ["error"]


# --- criterion 1 (R2.5): impersonation_denied lands in audit_events --------------------------


def test_03b_1_obo_denied_writes_audit(pg):
    token = sign_on_behalf_of(
        user_id=USER, project_id=PROJECT, audience="ffcore-backend", settings=SETTINGS
    )
    before = len(_rows(pg, "impersonation_denied"))
    response = _app().get("/whoami", headers={"X-On-Behalf-Of": token})
    assert response.status_code == 401
    rows = _rows(pg, "impersonation_denied")
    assert len(rows) == before + 1
    actor_type, actor_id, _, _, outcome, _, after, _, _ = rows[-1]
    assert (actor_type, actor_id, outcome) == ("system", "anonymous", "denied")
    assert token not in json.dumps(after)


def test_03b_1_valid_obo_actor_is_user_in_audit(pg):
    token = sign_on_behalf_of(
        user_id=USER, project_id=PROJECT, audience="ffcore-backend", settings=SETTINGS
    )
    response = _app().post(
        "/obo-things",
        headers={
            "Authorization": "Bearer dummy-not-secret-service-token-0123456789",
            "X-On-Behalf-Of": token,
        },
    )
    assert response.status_code == 200
    rows = _rows(pg, "thing.obo")
    assert [(row[0], row[1], row[2]) for row in rows] == [("user", USER, PROJECT)]


# --- review r1 MAJOR-3: failures anywhere in the managed transaction are audited -------------

_probe_metadata = MetaData()
_unique_probe = Table(
    "t03b_unique_probe", _probe_metadata, Column("code", String, primary_key=True)
)


class _UniqueProbe:
    def __init__(self, code: str) -> None:
        self.code = code


registry().map_imperatively(_UniqueProbe, _unique_probe)


def _failure_app() -> TestClient:
    app = FastAPI()
    install_error_handlers(app)

    @app.post("/duplicate")
    @audited("probe.duplicate", "probe")
    async def duplicate(
        request: Request,
        actor: Annotated[Actor, Depends(user_actor)],
        session: Annotated[AsyncSession, Depends(db.get_session)],
    ):
        # Pending ORM object; the constraint fails only when the decorator flushes.
        session.add(_UniqueProbe("dup"))
        return {"id": "dup", "api_key": "dummy-not-secret-probe"}

    async def broken_before(**_):
        raise RuntimeError("cannot load before state")

    @app.post("/before-fails")
    @audited("probe.before", "probe", load_before=broken_before)
    async def before_fails(
        request: Request,
        actor: Annotated[Actor, Depends(user_actor)],
        session: Annotated[AsyncSession, Depends(db.get_session)],
    ):
        return {"id": "never"}

    return TestClient(app, raise_server_exceptions=False)


def test_03b_5_flush_failure_audited_and_rolled_back(pg):
    pg.execute("CREATE TABLE IF NOT EXISTS t03b_unique_probe (code text PRIMARY KEY)")
    pg.execute("INSERT INTO t03b_unique_probe VALUES ('dup') ON CONFLICT DO NOTHING")
    response = _failure_app().post("/duplicate")
    assert response.status_code == 500
    rows = _rows(pg, "probe.duplicate")
    assert [row[4] for row in rows] == ["error"]
    assert rows[0][6] is None  # no content for a failed mutation
    assert "dummy-not-secret" not in response.text
    assert pg.execute("SELECT count(*) FROM t03b_unique_probe").fetchone()[0] == 1


def test_03b_5_load_before_failure_audited(pg):
    response = _failure_app().post("/before-fails")
    assert response.status_code == 500
    assert [row[4] for row in _rows(pg, "probe.before")] == ["error"]


def test_03b_5_audit_write_failure_is_loud(pg, monkeypatch):
    import ffcore.core.audit as audit_module

    async def unavailable(entry):
        raise ConnectionError("audit store unavailable")

    monkeypatch.setattr(audit_module, "write_event_detached", unavailable)
    client = _failure_app()
    with pytest.raises(audit_module.AuditWriteError) as exc:
        TestClient(client.app).post("/before-fails")
    assert isinstance(exc.value.__cause__, ConnectionError)
    assert exc.value.__notes__ == ["original failure: RuntimeError"]
