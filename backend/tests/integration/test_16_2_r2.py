"""16-2 r2 (R-16-0013): a Jira comment the source restricts, or a service desk internal note,
never reaches the index (A2 scenario, through the engine); a scheduled run becomes a full run
when the last completed full is FULL_SYNC_EVERY_DAYS old (a narrowed permission reaches the
index without anyone starting a full run)."""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ffcore.sources import scheduler
from tests.integration import sources_support, test_16_2_atlassian
from tests.integration.sources_support import (
    RecordingQueue,
    create_fs_source,
    drain,
    found,
    sources_url,
    sync,
    write_tree,
)
from tests.integration.test_16_2_atlassian import (
    PAT,
    PROSE,
    control,
    create_source,
    full,
    issue,
    open_to_analysts,
)

src_world = sources_support.src_world
atl = test_16_2_atlassian.atl


def test_16_2_r2_restricted_comments_never_reach_the_index(atl, pg):
    w = atl
    comments = [
        {"body": f"{PROSE} acikyorum", "created": "2026-03-01T10:00:00.000+0300"},
        {"body": f"{PROSE} gizliyorum", "visibility": {"type": "role", "value": "Administrators"}},
        {"body": f"{PROSE} ekipyorum", "visibility": {"type": "group", "value": "jira-ops"}},
        {"body": f"{PROSE} icnotum", "jsdPublic": False},
    ]
    control(
        w,
        "/_state",
        {
            "auth": [f"Bearer {PAT}"],
            "jira": {"projects": {"OPS": {}}, "issues": [issue(1, comment={"comments": comments})]},
        },
    )
    source = create_source(w, kind="jira", key="jira", config={"jql": "project = OPS"})
    open_to_analysts(w, source["id"], group="project:OPS")
    raw, *_ = full(w, source["id"])
    assert raw["added"] == 1
    assert found(w, "analyst", "acikyorum")
    for hidden in ("gizliyorum", "ekipyorum", "icnotum"):
        assert not found(w, "analyst", hidden) and not found(w, "admin", hidden), hidden
    texts = pg.execute(
        "SELECT c.text FROM chunks c JOIN documents d ON d.id = c.document_id WHERE d.kb_id = %s",
        (w["kb"],),
    ).fetchall()
    assert texts and not any("gizliyorum" in t or "icnotum" in t for (t,) in texts)
    # The source's own bytes keep them (raw is the API answer as is; D3).
    (raw_path,) = pg.execute(
        "SELECT raw_path FROM source_items WHERE data_source_id = %s", (source["id"],)
    ).fetchone()
    assert "gizliyorum" in Path(raw_path).read_text(encoding="utf-8")


def _tick(w, now):
    queue = RecordingQueue()
    result = asyncio.run(scheduler.tick(now=now, settings=w["settings"], sync_queue=queue))
    return result, queue


def test_16_2_r2_scheduled_run_is_full_once_a_week(src_world, pg):
    w = src_world
    write_tree(w["root"], {"a.md": "# A\n\nmetin"})
    source = create_fs_source(w, schedule={"kind": "daily", "at": "02:00"})
    sync(w, source["id"], mode="full")
    drain(w)
    now = datetime.now(UTC).replace(hour=2, minute=0, second=30, microsecond=0)

    def last_full_ended(days):
        pg.execute(
            "UPDATE sync_runs SET started_at = %s, ended_at = %s WHERE data_source_id = %s",
            (now - timedelta(days=days), now - timedelta(days=days), source["id"]),
        )

    def scheduled_mode():
        result, queue = _tick(w, now)
        assert len(result["started"]) == 1, result
        (_, run_id) = queue.jobs[0]
        mode = pg.execute("SELECT mode FROM sync_runs WHERE id = %s", (run_id,)).fetchone()[0]
        pg.execute("DELETE FROM sync_runs WHERE id = %s", (uuid.UUID(run_id),))  # never ran
        return mode

    last_full_ended(8)
    assert scheduled_mode() == "full"
    last_full_ended(2)
    assert scheduled_mode() == "delta"
    w["settings"] = w["settings"].model_copy(update={"full_sync_every_days": 0})
    last_full_ended(30)
    assert scheduled_mode() == "delta"
    # The database is shared: the source must not be due in the other scheduler tests' ticks.
    paused = w["admin"].patch(sources_url(w, f"/{source['id']}"), json={"status": "paused"})
    assert paused.status_code == 200, paused.text
