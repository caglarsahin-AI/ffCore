"""04b-1 D2 through the API (real app, real database, fake models and queue).

Acceptance 6: the ingest report counts source x gate x reason and lists rejected documents and
chunks; a preset reconversion queues only its targets. FOLLOWUP-86: the document ACL can be
edited after upload; the search response lists what the thresholds filtered. FOLLOWUP-133:
deleting a document removes its silver and text_raw files, raw stays (D3).
"""

from pathlib import Path

from tests.integration import test_04a_api as kb_api
from tests.integration.conftest import audit_rows
from tests.integration.test_04a_api import PROSE, create_kb, kb_url, process_all, search, upload

# 04a's fixtures (fake embedder, ingest queue, users of two projects), used as they are.
queue = kb_api.queue
settings = kb_api.settings
world = kb_api.world


def doc_url(world, kb_id, document_id):
    return f"{kb_url(world, kb_id)}/documents/{document_id}"


def upload_bytes(world, client, kb_id, name, data: bytes, **form):
    files = {"files": (name, data, "application/octet-stream")}
    return client.post(f"{kb_url(world, kb_id)}/documents", files=files, data=form)


def test_04b_6_ingest_report_source_gate_reason(world, settings, queue):
    kb = create_kb(world)
    good = "\n\n".join(f"## Madde {i}\n\n{PROSE * 6}" for i in range(1, 4))
    upload(world, world["admin"], kb["id"], "iyi.md", good)
    upload(world, world["admin"], kb["id"], "kisa.md", "kisa")
    upload_bytes(world, world["admin"], kb["id"], "arac.exe", b"MZ" + bytes(100))
    process_all(settings, queue)

    response = world["admin_read"].get(f"{kb_url(world, kb['id'])}/ingest-report")
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["documents"] == 3
    per_gate: dict[str, int] = {}
    for row in report["gates"]:
        assert set(row) == {"source", "gate", "status", "reason", "documents"}
        assert row["source"] == "upload"
        per_gate[row["gate"]] = per_gate.get(row["gate"], 0) + row["documents"]
    assert per_gate == {"gate0": 3, "gate1": 3, "gate2": 3}  # totals equal the documents
    rejected = {d["filename"]: d for d in report["rejected_documents"]}
    assert set(rejected) == {"kisa.md", "arac.exe"}
    assert (rejected["arac.exe"]["gate"], rejected["arac.exe"]["reason"]) == ("gate0", "binary")
    assert rejected["kisa.md"]["gate"] in {"gate1", "gate2"} and rejected["kisa.md"]["reason"]
    assert report["rejected_documents_total"] == 2
    assert report["by_status"]["indexed"] == 1 and report["by_status"]["skipped"] == 2
    assert isinstance(report["rejected_chunks"], list)
    assert report["rejected_chunks_total"] == len(report["rejected_chunks"])


def test_04b_6_ingest_report_respects_document_acl(world, settings, queue):
    kb = create_kb(world)
    upload_bytes(
        world, world["admin"], kb["id"], "gizli.exe", b"MZ" + bytes(100), acl_roles="admin"
    )
    upload_bytes(world, world["admin"], kb["id"], "acik.exe", b"MZ" + bytes(100))
    process_all(settings, queue)
    report = world["analyst"].get(f"{kb_url(world, kb['id'])}/ingest-report").json()
    assert report["documents"] == 1
    assert [d["filename"] for d in report["rejected_documents"]] == ["acik.exe"]


def test_04b_86_document_acl_edit_reaches_search(world, settings, queue, pg):
    kb = create_kb(world)
    item = upload(world, world["admin"], kb["id"], "a.md", PROSE * 8).json()["data"][0]
    process_all(settings, queue)
    url = doc_url(world, kb["id"], item["document"]["id"])
    assert search(world["analyst"], world, kb["id"], "fesih").json()["hits"]

    response = world["admin"].patch(url, json={"acl_roles": ["admin"]})
    assert response.status_code == 200, response.text
    assert response.json()["acl_roles"] == ["admin"]
    assert search(world["analyst"], world, kb["id"], "fesih").json()["hits"] == []
    assert len(audit_rows(pg, "update_document", "success", project=world["project"])) == 1

    conflict = world["admin"].patch(url, json={"acl_open": True, "acl_roles": ["admin"]})
    assert conflict.status_code == 422 and conflict.json()["error"]["code"] == "acl_conflict"
    empty = world["admin"].patch(url, json={"acl_roles": [], "acl_users": []})
    assert empty.status_code == 422 and empty.json()["error"]["code"] == "acl_empty"
    read_only = world["admin_read"].patch(url, json={"acl_open": True})
    assert read_only.status_code == 403

    opened = world["admin"].patch(url, json={"acl_open": True})
    assert opened.status_code == 200 and opened.json()["acl_roles"] == []
    assert search(world["analyst"], world, kb["id"], "fesih").json()["hits"]


def test_04b_86_search_response_lists_filtered_and_truncated(world, settings, queue):
    kb = create_kb(world)
    upload(world, world["analyst"], kb["id"], "a.md", PROSE * 8)
    process_all(settings, queue)
    body = search(world["analyst"], world, kb["id"], "fesih").json()
    assert isinstance(body["filtered"], list) and isinstance(body["rerank_truncated"], int)
    for row in body["filtered"]:
        assert row["reason"] in {"below_rerank_floor", "below_min_score"}


def test_04b_6_preset_reindex_queues_targets_only(world, settings, queue, pg):
    kb = create_kb(world)
    upload(world, world["analyst"], kb["id"], "iyi.md", PROSE * 8)
    upload_bytes(
        world, world["analyst"], kb["id"], "bozuk.txt", b"ok\n\x81\x8d bozuk\n" + b"x" * 99
    )
    process_all(settings, queue)
    url = f"{kb_url(world, kb['id'])}/reindex"

    response = world["analyst"].post(url, json={"layer": "silver", "preset": "encoding"})
    assert response.status_code == 202, response.text
    assert response.json()["documents"] == 1 and response.json()["preset"] == "encoding"
    assert queue.jobs == [("reindex_job", kb["id"], "silver", False, False, "encoding")]

    gold = world["analyst"].post(url, json={"layer": "gold", "preset": "timeout"})
    assert gold.status_code == 422 and gold.json()["error"]["code"] == "preset_requires_silver"
    bogus = world["analyst"].post(url, json={"layer": "silver", "preset": "bogus"})
    assert bogus.status_code == 422


def test_04b_133_delete_removes_silver_and_text_raw_keeps_raw(world, settings, queue, pg):
    kb = create_kb(world)
    item = upload(world, world["analyst"], kb["id"], "a.md", PROSE * 8).json()["data"][0]
    process_all(settings, queue)
    raw, silver = pg.execute(
        "SELECT raw_path, silver_path FROM documents WHERE id = %s", (item["document"]["id"],)
    ).fetchone()
    silver = Path(silver)
    text_raw = silver.with_suffix(".raw.md")
    assert Path(raw).exists() and silver.exists() and text_raw.exists()

    response = world["analyst"].delete(doc_url(world, kb["id"], item["document"]["id"]))
    assert response.status_code == 204
    assert not silver.exists() and not text_raw.exists()
    assert Path(raw).exists()  # D3: raw stays (the runbook removes it)
    (silver_path,) = pg.execute(
        "SELECT silver_path FROM documents WHERE id = %s", (item["document"]["id"],)
    ).fetchone()
    assert silver_path is None


def test_04b_133_kb_delete_removes_silver_of_every_document(world, settings, queue, pg):
    kb = create_kb(world)
    for name in ("a.md", "b.md"):
        upload(world, world["admin"], kb["id"], name, PROSE * 8 + name)
    process_all(settings, queue)
    silvers = [
        Path(p)
        for (p,) in pg.execute(
            "SELECT silver_path FROM documents WHERE kb_id = %s", (kb["id"],)
        ).fetchall()
    ]
    assert len(silvers) == 2 and all(p.exists() for p in silvers)
    assert world["admin"].delete(kb_url(world, kb["id"])).status_code == 204
    assert not any(p.exists() or p.with_suffix(".raw.md").exists() for p in silvers)
