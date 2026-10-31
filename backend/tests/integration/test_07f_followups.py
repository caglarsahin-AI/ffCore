"""fix/07-followups with the real graph, runner, run API, Postgres and Redis.

FOLLOWUP-104: the approval TTL closes a waiting run, its `error` row is committed but the live
entry is lost (Redis error after the first event): a reconnecting client still gets `error`.
"""

import asyncio
import threading
from datetime import UTC, datetime, timedelta

import pytest
from redis import exceptions as redis_errors

from ffcore.runtime import events as run_events
from ffcore.runtime.contracts import SseEvent
from tests.integration.runs_fixtures import *  # noqa: F403 - fixtures
from tests.integration.runs_fixtures import get_stream
from tests.integration.runtime_support import events, run_row
from tests.integration.test_07_flow import _waiting, team  # noqa: F401 - fixture

STREAM_LIMIT_S = 20


def _stream_within(client, project_id, run_id, last):
    """The reconnect, in a daemon thread: a stream that never ends fails the test, not hangs it."""
    out: dict = {}

    def read():
        out["events"] = get_stream(client, project_id, run_id, last)

    worker = threading.Thread(target=read, daemon=True)
    worker.start()
    worker.join(STREAM_LIMIT_S)
    assert not worker.is_alive(), "the stream did not end: the stored error never reached it"
    return out["events"]


def test_07f_2_expired_close_redis_publish_fails_reconnect_gets_error(
    team,  # noqa: F811 - the imported fixture
    pg,
    harness,
    use_queue,
    settings,
    monkeypatch,
):
    from ffcore.core import db
    from ffcore.services import approvals

    project_id, c = team
    run_id, streamed, *_ = _waiting(team, pg, harness, use_queue)
    last_id = streamed[-1][0]
    assert streamed[-1][1] == "approval_required"

    publish = run_events.RunEventWriter._publish

    async def failing(self, entry_id, sse, data):
        # The first event of the close (approval_expired, no live entry) is committed; the
        # error's live entry is where Redis fails.
        if sse is SseEvent.error:
            raise redis_errors.ConnectionError("redis went away")
        return await publish(self, entry_id, sse, data)

    monkeypatch.setattr(run_events.RunEventWriter, "_publish", failing)
    later = datetime.now(UTC) + timedelta(minutes=settings.approval_ttl_min, seconds=1)

    async def tick():
        async with db.session_scope() as session:
            return await approvals.expire_due(
                session, now=later, close_run=approvals.run_closer(settings)
            )

    with pytest.raises(RuntimeError):  # the sweep fails loud for the lost publish
        asyncio.run(tick())
    row = run_row(pg, run_id)
    assert (row["status"], row["error_code"]) == ("failed", "approval_expired")
    assert [t for _, t, _ in events(pg, run_id)][-2:] == ["approval_expired", "error"]

    replayed = _stream_within(c["owner"], project_id, run_id, last_id)
    assert replayed[-1][1] == "error"
    assert replayed[-1][2]["code"] == "approval_expired"
    assert [e for _, e, _ in replayed].count("error") == 1


# --- FOLLOWUP-111: the sweep test hook ------------------------------------------------------

SWEEP = "/api/v1/internal/approvals/sweep"


def _with_hooks(app, settings, enabled):
    from ffcore.core.config import get_settings

    pinned = settings.model_copy(update={"ffcore_test_hooks": enabled})
    app.dependency_overrides[get_settings] = lambda: pinned
    return pinned


@pytest.fixture
def hooks(app, settings):
    return _with_hooks(app, settings, True)


@pytest.fixture
def hooks_off(app, settings):
    # Pinned explicitly so the test holds whatever FFCORE_TEST_HOOKS the stack runs with.
    return _with_hooks(app, settings, False)


def _service(client_factory):
    from tests.dummy import SERVICE_TOKEN

    client = client_factory()
    client.headers.update({"Authorization": f"Bearer {SERVICE_TOKEN}"})
    return client


def test_07f_3_sweep_hook_404_when_flag_off(team, client_factory, hooks_off):  # noqa: F811
    assert hooks_off.ffcore_test_hooks is False  # a normal deployment: no hook
    unknown = _service(client_factory).post("/api/v1/internal/approvals/no-such-path")
    for client in (_service(client_factory), team[1]["analyst"]):
        response = client.post(SWEEP)
        # The same answer as a path that does not exist, before any identity check.
        assert (response.status_code, response.json()) == (404, unknown.json())


def test_07f_4_sweep_hook_expires_and_is_idempotent(
    team,  # noqa: F811 - the imported fixture
    pg,
    harness,
    use_queue,
    hooks,
    client_factory,
):
    run_id, *_ = _waiting(team, pg, harness, use_queue)
    [(approval_id,)] = pg.execute(
        "SELECT id FROM approvals WHERE run_id = %s", (run_id,)
    ).fetchall()
    service = _service(client_factory)
    early = datetime.now(UTC).isoformat()
    first = service.post(SWEEP, params={"now": early})
    assert first.status_code == 200, first.text
    assert str(approval_id) not in first.json()["expired"]  # not due yet
    later = datetime.now(UTC) + timedelta(minutes=hooks.approval_ttl_min, seconds=1)
    due = service.post(SWEEP, params={"now": later.isoformat()})
    assert due.status_code == 200, due.text
    assert str(approval_id) in due.json()["expired"]
    row = run_row(pg, run_id)
    assert (row["status"], row["error_code"]) == ("failed", "approval_expired")
    again = service.post(SWEEP, params={"now": later.isoformat()})
    assert again.status_code == 200 and str(approval_id) not in again.json()["expired"]
    assert [t for _, t, _ in events(pg, run_id)].count("approval_expired") == 1


def test_07f_5_sweep_hook_service_only_and_tz(team, hooks, client_factory):  # noqa: F811
    console = team[1]["analyst"].post(SWEEP)
    assert (console.status_code, console.json()["error"]["code"]) == (
        403,
        "service_account_required",
    )
    naive = _service(client_factory).post(SWEEP, params={"now": "2026-10-30T12:00:00"})
    assert (naive.status_code, naive.json()["error"]["code"]) == (422, "now_without_timezone")
