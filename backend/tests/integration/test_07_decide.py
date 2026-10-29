"""07 slice 3 (07 side): recording a decision. The route and the run resume (06a
`runtime.resume.resume_run`, same transaction) come in slice 6; this is the rule part.
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from ffcore.core import db
from ffcore.core.auth import SERVICE_ACTOR, Actor, Grant
from ffcore.core.errors import ApiError
from ffcore.services import approvals
from tests.integration.test_07_schema import _insert

NOW = datetime.now(UTC)
USER = Actor(actor_type="user", actor_id=str(uuid.uuid4()))
ADMIN = Grant("admin", "edit", False)


def _decide(database_url, project, approval_id, *, actor=USER, grant=ADMIN, now=None, **kw):
    async def go():
        db.configure(database_url, pooled=False)
        try:
            async with db.session_scope() as session:
                row = await approvals.decide(
                    session,
                    project_id=project,
                    approval_id=approval_id,
                    actor=actor,
                    grant=grant,
                    decision=kw.get("decision", "approved"),
                    note=kw.get("note"),
                    now=now or datetime.now(UTC),
                    request_id="req-07",
                )
                await session.commit()
                return row
        finally:
            db.reset()

    return asyncio.run(go())


def _audit(pg, approval_id, action):
    # The test database is shared by the session: select this approval's events only.
    return pg.execute(
        "SELECT actor_id, outcome, after FROM audit_events"
        " WHERE action = %s AND resource_id = %s ORDER BY ts",
        (action, str(approval_id)),
    ).fetchall()


def _code(excinfo):
    return excinfo.value.status_code, excinfo.value.code


def test_07_decision_audited(database_url, pg, make_project):
    project = make_project()
    row = _insert(pg, project)
    decided = _decide(database_url, project, row["id"], decision="rejected", note="wrong table")
    assert (decided.status, decided.resolved_by) == ("rejected", USER.actor_id)
    assert decided.resolution_note == "wrong table" and decided.resolved_at is not None
    [(actor_id, outcome, after)] = _audit(pg, row["id"], "approval.rejected")
    assert (actor_id, outcome) == (USER.actor_id, "success")
    assert after["arguments"] == {"sql": "SELECT 1"} and after["note"] == "wrong table"
    assert after["run_id"] == str(row["run_id"]) and after["action"] == "mcp-sql__run_sql"


def test_07_analyst_cannot_approve_developer_403(database_url, pg, make_project):
    project = make_project()
    row = _insert(pg, project, assigned_role="developer")
    with pytest.raises(ApiError) as denied:
        _decide(database_url, project, row["id"], grant=Grant("analyst", "edit", False))
    assert _code(denied) == (403, "insufficient_role")
    [(_, outcome, after)] = _audit(pg, row["id"], "approval.approved")
    assert outcome == "denied" and after == {"code": "insufficient_role"}
    pending = pg.execute("SELECT status FROM approvals WHERE id = %s", (row["id"],)).fetchone()
    assert pending == ("pending",)


def test_07_read_access_cannot_decide(database_url, pg, make_project):
    project = make_project()
    row = _insert(pg, project)
    with pytest.raises(ApiError) as denied:
        _decide(database_url, project, row["id"], grant=Grant("admin", "read", False))
    assert _code(denied) == (403, "read_only_access")


@pytest.mark.parametrize(
    "actor",
    [
        SERVICE_ACTOR,
        Actor(actor_type="user", actor_id=str(uuid.uuid4()), via_service=True),
        Actor(actor_type="api_key", actor_id="k1", scopes=frozenset({"impersonate"})),
    ],
    ids=["service", "on-behalf-of", "api-key"],
)
def test_07_decision_requires_console_session(database_url, pg, make_project, actor):
    project = make_project()
    row = _insert(pg, project)
    with pytest.raises(ApiError) as denied:
        _decide(database_url, project, row["id"], actor=actor)
    assert _code(denied) == (403, "approval_requires_user_session")


def test_07_second_decision_409(database_url, pg, make_project):
    project = make_project()
    row = _insert(pg, project)
    _decide(database_url, project, row["id"])
    with pytest.raises(ApiError) as again:
        _decide(database_url, project, row["id"], decision="rejected")
    assert _code(again) == (409, "approval_not_pending")


def test_07_decision_after_ttl_409(database_url, pg, make_project):
    project = make_project()
    row = _insert(pg, project, expires_at=NOW + timedelta(minutes=60))
    with pytest.raises(ApiError) as late:
        _decide(database_url, project, row["id"], now=NOW + timedelta(minutes=60))
    assert _code(late) == (409, "approval_expired")


def test_07_decision_other_project_404(database_url, pg, make_project):
    row = _insert(pg, make_project())
    with pytest.raises(ApiError) as missing:
        _decide(database_url, make_project(), row["id"])
    assert _code(missing) == (404, "approval_not_found")
