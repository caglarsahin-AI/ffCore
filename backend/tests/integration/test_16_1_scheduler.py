"""16-1 sync worker tick (K-16-0002 S2): a due schedule starts one raw delta run, a source never
synced and a manual one are not started, an active run keeps its slot, a run abandoned by a
dead worker is failed `run_abandoned`; and the CLI (`make sync`) queues like the API."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from ffcore.sources import cli, engine, scheduler
from tests.integration import sources_support
from tests.integration.conftest import audit_rows
from tests.integration.sources_support import (
    RecordingQueue,
    create_fs_source,
    drain,
    runs,
    sources_url,
    sync,
    write_tree,
)

src_world = sources_support.src_world


def tick(w, now):
    queue = RecordingQueue()
    result = asyncio.run(scheduler.tick(now=now, settings=w["settings"], sync_queue=queue))
    return result, queue


def test_16_1_tick_starts_due_schedules_only(src_world, pg):
    w = src_world
    write_tree(w["root"], {"a.md": "# A\n\nmetin"})
    daily = create_fs_source(w, key="gunluk", schedule={"kind": "daily", "at": "02:00"})
    manual = create_fs_source(w, key="elle", schedule={"kind": "manual"})
    never = create_fs_source(w, key="hic", schedule={"kind": "hourly", "minute": 0})
    for source in (daily, manual):
        sync(w, source["id"])
        drain(w)
    pg.execute(
        "UPDATE sync_runs SET started_at = %s WHERE data_source_id = %s",
        (datetime(2026, 11, 21, 1, 0, tzinfo=UTC), daily["id"]),
    )
    result, queue = tick(w, datetime(2026, 11, 22, 2, 0, 30, tzinfo=UTC))
    assert len(result["started"]) == 1 and result["abandoned"] == 0
    (function, run_id) = queue.jobs[0]
    assert function == engine.SYNC_RAW_JOB
    run = pg.execute(
        "SELECT data_source_id, layer, mode, trigger, requested_by, status FROM sync_runs"
        " WHERE id = %s",
        (run_id,),
    ).fetchone()
    assert run == (uuid.UUID(daily["id"]), "raw", "delta", "schedule", "system:schedule", "queued")
    # The same slot again: the queued run holds it (one active run per source).
    again, queue = tick(w, datetime(2026, 11, 22, 2, 1, tzinfo=UTC))
    assert again["started"] == [] and queue.jobs == []
    assert never["id"] not in {
        str(r[0]) for r in pg.execute("SELECT data_source_id FROM sync_runs").fetchall()
    }


# r3 (R-16-0006 MAJOR-1 `saate-bagli-test`): the tick runs on an injected clock, never the wall
# clock; three times of day, before, inside and after the 02:00 daily slot's 13-hour shadow
# (the abandon limit). Today's UTC date keeps the other sources of the shared database off-slot.
TODAY = datetime.now(UTC).date()
TICK_TIMES = [
    datetime(TODAY.year, TODAY.month, TODAY.day, 1, 30, tzinfo=UTC),
    datetime(TODAY.year, TODAY.month, TODAY.day, 8, 14, tzinfo=UTC),
    datetime(TODAY.year, TODAY.month, TODAY.day, 23, 50, tzinfo=UTC),
]


def _abandon(pg, run_id, now):
    pg.execute(
        "UPDATE sync_runs SET status = 'running', started_at = %s WHERE id = %s",
        (now - scheduler.ABANDON_AFTER - timedelta(minutes=1), run_id),
    )


@pytest.mark.parametrize("now", TICK_TIMES, ids=lambda n: n.strftime("%H%M"))
def test_16_1_tick_fails_abandoned_runs(src_world, pg, now):
    w = src_world
    source = create_fs_source(w, schedule={"kind": "manual"})
    run = sync(w, source["id"])
    w["sync_queue"].jobs.clear()
    _abandon(pg, run["id"], now)
    result, _ = tick(w, now)
    assert result["abandoned"] >= 1
    status, error = pg.execute(
        "SELECT status, error FROM sync_runs WHERE id = %s", (run["id"],)
    ).fetchone()
    assert (status, error) == ("failed", "run_abandoned")
    assert [r for r in runs(w, source["id"]) if r["status"] == "queued"] == []
    # A manual source gets no run from the tick: it can sync again at once.
    assert w["admin"].post(sources_url(w, f"/{source['id']}/sync"), json={}).status_code == 202


def test_16_1_tick_abandon_then_the_daily_slot_takes_over(src_world, pg):
    """The other side of the same rule, pinned: a daily source whose run was abandoned before
    today's 02:00 slot gets that slot's run in the same tick, so a manual sync right after is
    409 sync_running (one active run per source), not a second run."""
    w = src_world
    now = TICK_TIMES[1]  # 08:14, inside the slot's shadow
    source = create_fs_source(w, schedule={"kind": "daily", "at": "02:00"})
    run = sync(w, source["id"])
    w["sync_queue"].jobs.clear()
    _abandon(pg, run["id"], now)
    result, queue = tick(w, now)
    mine = [r for r in runs(w, source["id"]) if r["trigger"] == "schedule"]
    # r2 MINOR-1: its only full run was abandoned (no completed full), so the slot's run is full.
    assert len(mine) == 1 and mine[0]["status"] == "queued" and mine[0]["mode"] == "full"
    assert (engine.SYNC_RAW_JOB, mine[0]["id"]) in queue.jobs
    second = w["admin"].post(sources_url(w, f"/{source['id']}/sync"), json={})
    assert second.status_code == 409 and second.json()["error"]["code"] == "sync_running"


def test_16_1_cli_queues_and_audits_force_prune(src_world, pg, monkeypatch):
    w = src_world
    source = create_fs_source(w)
    project_key = pg.execute("SELECT key FROM projects WHERE id = %s", (w["project"],)).fetchone()[
        0
    ]
    sync_queue, ingest_queue = RecordingQueue(), RecordingQueue()
    monkeypatch.setattr(scheduler, "get_sync_queue", lambda settings: sync_queue)
    monkeypatch.setattr(cli, "get_queue", lambda settings: ingest_queue)

    run_id = asyncio.run(
        cli.queue_sync(project_key, "paylasim", "raw", "full", True, settings=w["settings"])
    )
    assert sync_queue.jobs == [(engine.SYNC_RAW_JOB, run_id)]
    row = pg.execute(
        "SELECT trigger, requested_by, force_prune FROM sync_runs WHERE id = %s", (run_id,)
    ).fetchone()
    assert row == ("cli", "cli", True)
    assert audit_rows(pg, "sync_force_prune", "success", project=w["project"])
    for args, code in (
        ((project_key, "paylasim", "gold", "full", False), "sync_running"),
        ((project_key, "yok", "raw", "full", False), "data_source_not_found"),
        ((project_key, "paylasim", "raw", "delta", True), "force_prune_requires_full"),
    ):
        try:
            asyncio.run(cli.queue_sync(*args, settings=w["settings"]))
        except cli.CliRefused as exc:
            assert str(exc).startswith(code), exc
        else:
            raise AssertionError(f"{args} was not refused")
    assert source["id"]
