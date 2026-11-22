"""16-1 sync worker tick (K-16-0002 S2): a due schedule starts one raw delta run, a source never
synced and a manual one are not started, an active run keeps its slot, a run abandoned by a
dead worker is failed `run_abandoned`; and the CLI (`make sync`) queues like the API."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from ffcore.sources import cli, engine, scheduler
from tests.integration import sources_support
from tests.integration.conftest import audit_rows
from tests.integration.sources_support import (
    RecordingQueue,
    create_fs_source,
    drain,
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
    assert never["id"] not in {str(r[0]) for r in pg.execute("SELECT data_source_id FROM sync_runs").fetchall()}


def test_16_1_tick_fails_abandoned_runs(src_world, pg):
    w = src_world
    source = create_fs_source(w)
    run = sync(w, source["id"])
    w["sync_queue"].jobs.clear()
    pg.execute(
        "UPDATE sync_runs SET status = 'running', started_at = %s WHERE id = %s",
        (datetime.now(UTC) - scheduler.ABANDON_AFTER - timedelta(minutes=1), run["id"]),
    )
    result, _ = tick(w, datetime.now(UTC))
    assert result["abandoned"] == 1
    status, error = pg.execute(
        "SELECT status, error FROM sync_runs WHERE id = %s", (run["id"],)
    ).fetchone()
    assert (status, error) == ("failed", "run_abandoned")
    # The source can sync again.
    assert w["admin"].post(sources_url(w, f"/{source['id']}/sync"), json={}).status_code == 202


def test_16_1_cli_queues_and_audits_force_prune(src_world, pg, monkeypatch):
    w = src_world
    source = create_fs_source(w)
    project_key = pg.execute("SELECT key FROM projects WHERE id = %s", (w["project"],)).fetchone()[0]
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
