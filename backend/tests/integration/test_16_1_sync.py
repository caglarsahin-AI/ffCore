"""16-1 acceptance on a real network folder: three layers, the safe delete rule (D4), per item
errors, permissions (C15) and the layers that never ask the source (D3).

Kabul kriterleri (plan/16) proved here: delta reindexes only the changed item; items really
deleted (ratio under the limit) leave every layer in a full run; a mass disappearance is
`prune_refused` with an alert and deletes nothing; a listing cut in the middle or a count that
moves is `count_mismatch` (never forced); a delta never deletes without tombstones; an item error
does not stop the others; an unmapped group is admin only and a folder mapping narrows a
subtree; gold full and silver full make no request to the source and reuse unchanged vectors.
"""

import asyncio
import shutil
import uuid
from pathlib import Path

import pytest

from ffcore.sources import engine
from ffcore.sources.base import SourceError
from ffcore.sources.fs import FsDriver
from tests.integration.conftest import audit_rows
from tests.integration import sources_support
from tests.integration.sources_support import (
    API,
    age_tree,
    create_fs_source,
    document_text,
    documents,
    drain,
    found,
    runs,
    sources_url,
    sync,
    write_tree,
)

src_world = sources_support.src_world

TWENTY = {f"belgeler/belge-{n:02d}.md": document_text(f"Belge {n}", f"iz{n:02d}x") for n in range(20)}


def full_sync(w, source_id, **extra):
    sync(w, source_id, mode="full", **extra)
    return drain(w)


def raw_run(w, source_id):
    return next(r for r in runs(w, source_id) if r["layer"] == "raw")


def open_to_analysts(w, source_id):
    response = w["admin"].put(
        sources_url(w, f"/{source_id}/acl-mappings"),
        json={"mappings": [{"external_group": "*", "role": "analyst"}]},
    )
    assert response.status_code == 200, response.text


def test_16_1_full_then_delta_reindexes_only_the_changed_file(src_world, pg):
    w = src_world
    write_tree(w["root"], TWENTY)
    age_tree(w["root"])
    source = create_fs_source(w)
    open_to_analysts(w, source["id"])
    results = full_sync(w, source["id"])
    raw, silver = results
    assert raw["status"] == "completed" and raw["added"] == 20 and raw["prune_decision"] == "none"
    assert silver["status"] == "completed" and silver["added"] == 20
    docs = documents(pg, w["kb"])
    assert len(docs) == 20 and {d[3] for d in docs} == {"indexed"}
    assert all(d[1].startswith("paylasim/belgeler/") for d in docs)
    assert found(w, "analyst", "iz07x")

    (w["root"] / "belgeler" / "belge-07.md").write_text(
        document_text("Belge 7", "yeni-iz07y"), encoding="utf-8"
    )
    sync(w, source["id"], mode="delta")
    raw, silver = drain(w)
    assert (raw["listed"], raw["updated"], raw["added"], raw["deleted"]) == (1, 1, 0, 0)
    assert (silver["listed"], silver["updated"], silver["added"]) == (1, 1, 0)
    versions = {d[1]: d[2] for d in documents(pg, w["kb"])}
    assert versions["paylasim/belgeler/belge-07.md"] == 2
    assert {v for name, v in versions.items() if not name.endswith("belge-07.md")} == {1}
    assert found(w, "analyst", "yeni-iz07y")


def test_16_1_delta_without_changes_touches_nothing(src_world, pg):
    w = src_world
    write_tree(w["root"], dict(list(TWENTY.items())[:3]))
    age_tree(w["root"])
    source = create_fs_source(w)
    full_sync(w, source["id"])
    sync(w, source["id"], mode="delta")
    (raw,) = drain(w)  # nothing changed: no silver run
    assert raw["listed"] == 0 and raw["prune_decision"] == "none"
    assert {d[2] for d in documents(pg, w["kb"])} == {1}


def test_16_1_full_removes_three_deleted_files_from_every_layer(src_world, pg):
    w = src_world
    write_tree(w["root"], TWENTY)
    source = create_fs_source(w)
    open_to_analysts(w, source["id"])
    full_sync(w, source["id"])
    gone = ["belgeler/belge-03.md", "belgeler/belge-04.md", "belgeler/belge-05.md"]
    before = {
        row[0]: (row[1], row[2])
        for row in pg.execute(
            "SELECT external_id, raw_path, document_id FROM source_items"
            " WHERE data_source_id = %s",
            (source["id"],),
        ).fetchall()
    }
    silver = {
        row[0]: row[1]
        for row in pg.execute(
            "SELECT id, silver_path FROM documents WHERE id = ANY(%s)",
            ([before[g][1] for g in gone],),
        ).fetchall()
    }
    for rel in gone:
        (w["root"] / rel).unlink()
    (raw,) = full_sync(w, source["id"])
    # 3 of the 17 the source still holds: 0.18 <= PRUNE_MAX_RATIO 0.2 (C20 denominator).
    assert raw["prune_decision"] == "done" and raw["deleted"] == 3
    assert (raw["count_before"], raw["count_after"]) == (17, 17)
    for rel in gone:
        raw_path, document_id = before[rel]
        assert not Path(raw_path).parent.exists()  # raw: the item's tree is gone
        assert not Path(silver[document_id]).exists()  # silver
        deleted_at, chunks = pg.execute(
            "SELECT deleted_at, (SELECT count(*) FROM chunks WHERE document_id = d.id)"
            " FROM documents d WHERE id = %s",
            (document_id,),
        ).fetchone()
        assert deleted_at is not None and chunks == 0  # gold
        assert not found(w, "analyst", f"iz{rel[-5:-3]}x")
    states = dict(
        pg.execute(
            "SELECT external_id, state FROM source_items WHERE data_source_id = %s",
            (source["id"],),
        ).fetchall()
    )
    assert {states[g] for g in gone} == {"deleted"} and len(documents(pg, w["kb"])) == 17


def test_16_1_mass_disappearance_is_refused_with_an_alert_then_forced(src_world, pg):
    w = src_world
    rule = w["admin"].post(
        f"{API}/projects/{w['project']}/alert-rules", json={"kind": "prune_refused", "channel": "ui"}
    )
    assert rule.status_code in (200, 201), rule.text
    write_tree(w["root"], TWENTY)
    source = create_fs_source(w)
    full_sync(w, source["id"])
    # The share disappears (the mount lost a directory, a permission was withdrawn).
    shutil.rmtree(w["root"] / "belgeler")
    write_tree(w["root"], {f"belgeler/belge-{n:02d}.md": TWENTY[f"belgeler/belge-{n:02d}.md"] for n in range(10)})
    (raw,) = full_sync(w, source["id"])
    assert raw["prune_decision"] == "prune_refused" and raw["deleted"] == 0
    assert len(documents(pg, w["kb"])) == 20
    (payload,) = pg.execute(
        "SELECT payload FROM alerts WHERE kind = 'prune_refused' AND project_id = %s",
        (w["project"],),
    ).fetchone()
    assert payload["to_delete"] == 10 and payload["count_after"] == 10
    assert payload["data_source_id"] == source["id"]
    listed = w["admin"].get(sources_url(w, f"/{source['id']}")).json()
    assert listed["last_error"] is None and listed["active_run"] is None

    # force_prune is the admin's, on a full raw run only.
    refused = w["developer"].post(
        sources_url(w, f"/{source['id']}/sync"),
        json={"layer": "raw", "mode": "full", "force_prune": True},
    )
    assert refused.status_code == 403
    delta = w["admin"].post(
        sources_url(w, f"/{source['id']}/sync"),
        json={"layer": "raw", "mode": "delta", "force_prune": True},
    )
    assert delta.status_code == 422 and delta.json()["error"]["code"] == "force_prune_requires_full"
    (raw,) = full_sync(w, source["id"], force_prune=True)
    assert raw["prune_decision"] == "forced" and raw["deleted"] == 10
    assert len(documents(pg, w["kb"])) == 10
    assert audit_rows(pg, "sync_data_source", "success", project=w["project"])


def test_16_1_count_that_moves_deletes_nothing_even_forced(src_world, pg, monkeypatch):
    w = src_world
    write_tree(w["root"], TWENTY)
    source = create_fs_source(w)
    full_sync(w, source["id"])
    (w["root"] / "belgeler" / "belge-00.md").unlink()
    counts = iter([19, 18])  # the source changes between the two counts
    original = FsDriver.count

    async def moving(self):
        await original(self)
        return next(counts)

    monkeypatch.setattr(FsDriver, "count", moving)
    (raw,) = full_sync(w, source["id"], force_prune=True)
    assert raw["prune_decision"] == "count_mismatch" and raw["deleted"] == 0
    assert len(documents(pg, w["kb"])) == 20


def test_16_1_listing_cut_in_the_middle_deletes_nothing(src_world, pg, monkeypatch):
    w = src_world
    write_tree(w["root"], TWENTY)
    source = create_fs_source(w)
    full_sync(w, source["id"])
    state_before = pg.execute(
        "SELECT cursor FROM source_sync_state WHERE data_source_id = %s AND layer = 'raw'",
        (source["id"],),
    ).fetchone()
    original = FsDriver.list_changes

    async def broken(self, since):
        n = 0
        async for item in original(self, since):
            n += 1
            if n == 5:
                raise OSError("network share went away")  # the mount dropped
            yield item

    monkeypatch.setattr(FsDriver, "list_changes", broken)
    (raw,) = full_sync(w, source["id"])
    assert raw["status"] == "failed" and raw["prune_decision"] == "listing_failed"
    assert raw["deleted"] == 0 and len(documents(pg, w["kb"])) == 20
    assert {"code": "listing_failed", "detail": "OSError"} in raw["errors"]
    state_after = pg.execute(
        "SELECT cursor FROM source_sync_state WHERE data_source_id = %s AND layer = 'raw'",
        (source["id"],),
    ).fetchone()
    assert state_after == state_before  # the cursor did not move


def test_16_1_delta_never_deletes(src_world, pg):
    w = src_world
    write_tree(w["root"], TWENTY)
    source = create_fs_source(w)
    full_sync(w, source["id"])
    for n in range(3):
        (w["root"] / "belgeler" / f"belge-{n:02d}.md").unlink()
    sync(w, source["id"], mode="delta")
    (raw,) = drain(w)
    assert raw["prune_decision"] == "none" and raw["deleted"] == 0
    assert len(documents(pg, w["kb"])) == 20


def test_16_1_item_errors_are_isolated_and_listed(src_world, pg, tmp_path):
    w = src_world
    write_tree(w["root"], dict(list(TWENTY.items())[:5]))
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.md").write_text(document_text("dışarı", "sizinti"), encoding="utf-8")
    (w["root"] / "kacis.md").symlink_to(outside / "secret.md")
    (w["root"] / "bozuk.md").write_bytes(b"\xff\xfe\x00not markdown" * 10)
    source = create_fs_source(w)
    raw, silver = full_sync(w, source["id"])
    assert raw["status"] == "completed" and raw["added"] == 6 and raw["skipped"] == 1
    assert {"code": "path_outside_base", "external_id": "kacis.md", "detail": "refused while listing"} in raw["errors"]
    assert silver["added"] + silver["updated"] >= 5
    assert len([d for d in documents(pg, w["kb"]) if d[3] == "indexed"]) >= 5
    items = w["admin"].get(sources_url(w, f"/{source['id']}/items?errors=true")).json()
    assert [i["external_id"] for i in items["data"]] == ["kacis.md"]
    assert items["data"][0]["last_error"] == "path_outside_base"
    assert not found(w, "admin", "sizinti")
    # An item error keeps the cursor where it was: the next delta looks again.
    assert pg.execute(
        "SELECT cursor FROM source_sync_state WHERE data_source_id = %s AND layer = 'raw'",
        (source["id"],),
    ).fetchone() is None


def test_16_1_unmapped_items_are_admin_only_and_folders_narrow(src_world, pg):
    w = src_world
    write_tree(
        w["root"],
        {
            "genel/el-kitabi.md": document_text("El kitabı", "genelbilgi9"),
            "yonetim/kurul.md": document_text("Kurul", "kurulkarari9"),
        },
    )
    age_tree(w["root"])
    source = create_fs_source(w)
    full_sync(w, source["id"])
    assert not found(w, "analyst", "genelbilgi9")  # no mapping: admin only
    assert found(w, "admin", "genelbilgi9") and found(w, "admin", "kurulkarari9")
    items = w["admin"].get(sources_url(w, f"/{source['id']}/items")).json()["data"]
    assert {i["default_admin"] for i in items} == {True}

    mapping = w["admin"].put(
        sources_url(w, f"/{source['id']}/acl-mappings"),
        json={
            "mappings": [
                {"external_group": "folder:/", "role": "analyst"},
                {"external_group": "folder:/yonetim", "role": "admin"},
            ]
        },
    )
    assert mapping.status_code == 200
    assert w["developer"].put(
        sources_url(w, f"/{source['id']}/acl-mappings"), json={"mappings": []}
    ).status_code == 403
    # A delta that lists nothing still maps the stored groups again (C15, no source request).
    sync(w, source["id"], mode="delta")
    drain(w)
    assert found(w, "analyst", "genelbilgi9")
    assert not found(w, "analyst", "kurulkarari9")
    assert found(w, "admin", "kurulkarari9")
    (roles,) = pg.execute(
        "SELECT acl_roles FROM documents WHERE filename = 'paylasim/yonetim/kurul.md'"
        " AND deleted_at IS NULL"
    ).fetchone()
    assert roles == ["admin"]


def test_16_1_gold_and_silver_full_never_ask_the_source(src_world, pg, monkeypatch):
    w = src_world
    write_tree(w["root"], dict(list(TWENTY.items())[:6]))
    source = create_fs_source(w)
    full_sync(w, source["id"])
    chunks = pg.execute(
        "SELECT count(*) FROM chunks c JOIN documents d ON d.id = c.document_id"
        " WHERE d.kb_id = %s AND d.deleted_at IS NULL",
        (w["kb"],),
    ).fetchone()[0]
    assert chunks > 0
    calls = []

    def refuse(name):
        def call(*args, **kwargs):
            calls.append(name)
            raise AssertionError(f"the source was asked: {name}")

        return call

    for name in ("count", "list_changes", "fetch_raw", "list_attachments", "acl", "test_connection"):
        monkeypatch.setattr(FsDriver, name, refuse(name))
    shutil.rmtree(w["root"])  # even the folder itself is gone: raw is enough

    sync(w, source["id"], layer="gold", mode="full")
    (gold,) = drain(w)
    assert gold["status"] == "completed" and gold["reused"] == chunks and calls == []
    sync(w, source["id"], layer="silver", mode="full")
    (silver,) = drain(w)
    assert silver["status"] == "completed" and silver["listed"] == 6 and silver["errors"] == []
    assert calls == []
    assert {d[2] for d in documents(pg, w["kb"])} == {1}  # same bytes: no new version


def test_16_1_one_active_run_per_source(src_world):
    w = src_world
    source = create_fs_source(w)
    sync(w, source["id"])
    second = w["admin"].post(sources_url(w, f"/{source['id']}/sync"), json={"layer": "gold"})
    assert second.status_code == 409 and second.json()["error"]["code"] == "sync_running"
    assert w["admin"].get(sources_url(w, f"/{source['id']}")).json()["active_run"]["layer"] == "raw"
    drain(w)
    assert w["admin"].get(sources_url(w, f"/{source['id']}")).json()["active_run"] is None


def test_16_1_cancel_a_queued_run(src_world):
    w = src_world
    source = create_fs_source(w)
    run = sync(w, source["id"])
    cancelled = w["admin"].post(sources_url(w, f"/{source['id']}/runs/{run['id']}/cancel"))
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
    w["sync_queue"].jobs.clear()  # the worker would refuse it: no longer queued
    with pytest.raises(SourceError, match="run_not_queued"):
        asyncio.run(
            engine.run_raw(
                uuid.UUID(run["id"]),
                settings=w["settings"],
                store=None,
                ingest_queue=w["ingest_queue"],
            )
        )
    again = w["admin"].post(sources_url(w, f"/{source['id']}/runs/{run['id']}/cancel"))
    assert again.status_code == 409 and again.json()["error"]["code"] == "sync_run_finished"
