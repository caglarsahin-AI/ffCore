"""19: `ingest-raw` end to end on the synthetic PayCore-like tree (plan/19 kabul 1, şart 1-2).

The tree is copied to a read-only directory first: the command must work on a `:ro` mount and
write nothing under it. Raw bytes are unchanged; silver, text_raw and chunks are masked.
"""

import asyncio
import hashlib
import json
import os
import shutil
import stat
import uuid
from pathlib import Path

import pytest

from ffcore.knowledge import ingest, ingest_mask, raw_ingest
from ffcore.knowledge.convert.types import failed
from tests.converters import convert_without_weights
from tests.integration.test_04a_api import create_kb, queue, search, settings, world

__all__ = ["queue", "settings", "world"]  # fixtures used by name below

TREE = Path(__file__).resolve().parents[3] / "data" / "samples" / "paycore-like" / "raw"
SOURCES = ["confluence:DEMO", "jira:DEMO"]
PII_VALUES = ("destek@example.test", "0532 256 60 38", "10000000146")


@pytest.fixture
def ro_tree(tmp_path):
    target = tmp_path / "raw"
    shutil.copytree(TREE, target)
    modes = []
    for path in sorted(target.rglob("*"), reverse=True) + [target]:
        modes.append(path)
        path.chmod(stat.S_IREAD | (stat.S_IEXEC if path.is_dir() else 0))
    yield target
    for path in modes:
        path.chmod(stat.S_IRWXU)


def _project_key(pg, project_id):
    return pg.execute("SELECT key FROM projects WHERE id = %s", (project_id,)).fetchone()[0]


def _ingest(settings, project_key, kb_key, tree, **kw):
    return asyncio.run(
        raw_ingest.ingest_tree(
            text_filter="pii_regex",  # 19 measures the regex filter (08 tam 1b default pii_ner)
            project_key=project_key,
            kb_key=kb_key,
            raw_dir=tree,
            acl_roles=["analyst"],
            sources=kw.pop("sources", SOURCES),
            limit=kw.pop("limit", None),
            settings=settings,
            embed_client=kw.pop("embed_client", None) or ingest.LocalEmbedClient(settings),
            convert=kw.pop("convert", convert_without_weights),
        )
    )


def _snapshot(tree):
    return {
        str(p.relative_to(tree)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(tree.rglob("*"))
        if p.is_file()
    }


def test_19_1_ingest_raw_paycore_like_idempotent(world, pg, settings, ro_tree):
    kb = create_kb(world, key="paycore-like")
    key = _project_key(pg, world["project"])
    before = _snapshot(ro_tree)

    first = _ingest(settings, key, kb["key"], ro_tree)
    assert first.outcomes == {"created": 5}, first.lines()
    assert first.rejected == {"prsim_requires_ner": 1}
    assert first.statuses == {"indexed": 4, "skipped": 1}, first.lines()
    assert first.gates == {"gate2:boilerplate": 1}, first.lines()
    assert first.masked == {"EMAIL_ADDRESS": 1, "TR_PHONE": 1, "TR_NATIONAL_ID": 1}

    second = _ingest(settings, key, kb["key"], ro_tree)
    assert second.outcomes == {"unchanged": 5}, second.lines()
    assert "created 0" in second.lines()
    assert _snapshot(ro_tree) == before  # nothing written under the tree (şart 2)

    rows = pg.execute(
        "SELECT filename, version, raw_path, sha256, metadata FROM documents WHERE kb_id = %s",
        (kb["id"],),
    ).fetchall()
    assert {r[0] for r in rows} == {
        "confluence/DEMO/1001.md",
        "confluence/DEMO/1002.md",
        "confluence/DEMO/1003.md",
        "confluence/DEMO/1004.md",
        "jira/DEMO/DEMO-7.txt",
    }
    assert {r[1] for r in rows} == {1}  # the second run did not bump versions
    for _, _, raw_path, sha256, meta in rows:
        assert hashlib.sha256(Path(raw_path).read_bytes()).hexdigest() == sha256  # raw birebir
        assert meta["text_filter"] == f"pii_regex@{ingest_mask.PII_REGEX_VERSION}"
        assert "author" not in meta


def test_19_s1_pii_masked_in_silver_text_raw_and_chunks(world, pg, settings, ro_tree):
    kb = create_kb(world, key="paycore-mask")
    _ingest(settings, _project_key(pg, world["project"]), kb["key"], ro_tree)
    silver = pg.execute(
        "SELECT silver_path FROM documents WHERE kb_id = %s AND filename = %s",
        (kb["id"], "confluence/DEMO/1001.md"),
    ).fetchone()[0]
    silver_text = Path(silver).read_text(encoding="utf-8")
    text_raw = Path(silver).with_suffix(".raw.md").read_text(encoding="utf-8")
    raw_text = (ro_tree / "confluence/DEMO/1001.md").read_text(encoding="utf-8")
    chunks = " ".join(
        r[0] for r in pg.execute("SELECT text FROM chunks WHERE kb_id = %s", (kb["id"],))
    )
    for value in PII_VALUES:
        assert value in raw_text  # the source copy is not touched
        assert value not in silver_text and value not in text_raw and value not in chunks
    assert "[EMAIL_ADDRESS]" in silver_text and "[TR_PHONE]" in chunks


def test_19_1_search_returns_the_cited_source(world, pg, settings, ro_tree):
    kb = create_kb(world, key="paycore-search")
    _ingest(settings, _project_key(pg, world["project"]), kb["key"], ro_tree)
    response = search(world["analyst"], world, kb["id"], "fesih bildirim süresi kaç gün")
    assert response.status_code == 200, response.text
    hits = response.json()["hits"]
    # FAKE_EMBED vectors are not semantic: the claim is that the document is found with its
    # source breadcrumb, not its rank (the rank is a real-model measurement, make eval).
    fesih = [h for h in hits if h["document_name"] == "confluence/DEMO/1002.md"]
    assert fesih, [h["document_name"] for h in hits]
    assert "Üye İşyeri Sözleşmesi Fesih Kuralları" in fesih[0]["breadcrumb"]
    assert any("otuz gün" in h["text"] for h in fesih)


def test_19_1_limit_first_slice(world, pg, settings, ro_tree):
    kb = create_kb(world, key="paycore-slice")
    report = _ingest(settings, _project_key(pg, world["project"]), kb["key"], ro_tree, limit=2)
    assert report.outcomes == {"created": 2}, report.lines()


def test_19_s2_raw_dir_missing_and_kb_missing(world, pg, settings, tmp_path):
    key = _project_key(pg, world["project"])
    kb = create_kb(world, key="paycore-missing")
    with pytest.raises(raw_ingest.raw_staging.StagingError) as missing_dir:
        _ingest(settings, key, kb["key"], tmp_path / "absent")
    assert missing_dir.value.code == "raw_dir_missing"
    with pytest.raises(raw_ingest.RawIngestError) as err:
        _ingest(settings, key, "nope", tmp_path)
    assert err.value.code == "kb_not_found"


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file modes; the mount test runs :ro")
def test_19_s2_tree_is_read_only(ro_tree):
    with pytest.raises(PermissionError):
        (ro_tree / "x").write_text("x")


# --- corpus manifest (KARARLAR "M3 korpus kapsamı", K-M3S-0004) ---


def test_19_1_manifest_full_run(world, pg, settings, ro_tree):
    kb = create_kb(world, key="paycore-manifest")
    key = _project_key(pg, world["project"])
    report = _ingest(settings, key, kb["key"], ro_tree)
    manifest = report.manifest()
    assert manifest["stage"] == "full"
    assert manifest["documents"] == 5 and manifest["failed"] == 0 and manifest["timeout"] == 0
    assert manifest["sources"]["confluence:DEMO"]["documents"] == 4
    assert manifest["sources"]["jira:DEMO"]["documents"] == 1
    chunks = pg.execute(
        "SELECT count(*) FROM chunks c JOIN documents d ON d.id = c.document_id "
        "WHERE d.kb_id = %s AND c.chunk_status <> 'skipped'",
        (kb["id"],),
    ).fetchone()[0]
    assert manifest["chunks"] == chunks > 0
    assert manifest["rejected"] == {"prsim_requires_ner": 1}
    assert manifest["text_filter"].startswith("pii_regex@")
    assert len(manifest["raw_manifest_sha256"]) == 64
    # Same tree, second run: the manifest describes the same corpus (fixed for the baseline).
    again = _ingest(settings, key, kb["key"], ro_tree).manifest()
    assert again["raw_manifest_sha256"] == manifest["raw_manifest_sha256"]
    assert again["documents"] == 5 and again["chunks"] == manifest["chunks"]


def test_19_1_manifest_limit_is_pipeline_evidence(world, pg, settings, ro_tree):
    kb = create_kb(world, key="paycore-stage0")
    report = _ingest(settings, _project_key(pg, world["project"]), kb["key"], ro_tree, limit=2)
    manifest = report.manifest()
    assert manifest["stage"] == "stage0-pipeline-evidence"
    assert any("pipeline evidence" in line for line in report.lines())


def test_19_1_manifest_written_outside_raw_dir_only(world, pg, settings, ro_tree, tmp_path):
    kb = create_kb(world, key="paycore-mout")
    report = _ingest(settings, _project_key(pg, world["project"]), kb["key"], ro_tree)
    out = tmp_path / "out" / "manifest.json"
    raw_ingest.write_manifest(report, out, raw_dir=ro_tree)
    assert out.is_file()
    with pytest.raises(raw_ingest.RawIngestError) as err:
        raw_ingest.write_manifest(report, ro_tree / "manifest.json", raw_dir=ro_tree)
    assert err.value.code == "manifest_inside_raw_dir"


# --- PRSIM with --accept-personnel-data; customer data stops the ingest ---


def _prsim_tree(tmp_path, body):
    tree = tmp_path / "prsim"
    path = tree / "jira" / "PRSIM" / "PRSIM-1" / "PRSIM-1.md"
    path.parent.mkdir(parents=True)
    path.write_text(body, encoding="utf-8")
    meta = {"source": "jira:PRSIM", "source_item_id": "jira:PRSIM-1", "title": "PRSIM-1"}
    Path(f"{path}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return tree


PRSIM_BODY = (
    "# PRSIM-1 Yetki talebi\n\nBu talep, personelin raporlama uygulamasına erişebilmesi için "
    "açıldı ve bir gün içinde değerlendirildi. Yetki rolü tanımlandı, erişim test ortamında "
    "doğrulandı ve sonuç talep kaydına yazıldı. İletişim destek@example.test adresinden yapıldı; "
    "talep, kullanıcı onayından sonra kapatıldı ve ilgili ekip bilgilendirildi.\n"
)


def _ingest_prsim(settings, pg, world, kb_key, tree, accept):
    return asyncio.run(
        raw_ingest.ingest_tree(
            text_filter="pii_regex",  # 19 measures the regex filter (08 tam 1b default pii_ner)
            project_key=_project_key(pg, world["project"]),
            kb_key=kb_key,
            raw_dir=tree,
            acl_roles=["analyst"],
            sources=["jira:PRSIM"],
            limit=None,
            settings=settings,
            embed_client=ingest.LocalEmbedClient(settings),
            convert=convert_without_weights,
            accept_personnel_data=accept,
        )
    )


def test_19_s1_prsim_ingest_with_flag_masks_and_records(world, pg, settings, tmp_path):
    kb = create_kb(world, key="prsim")
    tree = _prsim_tree(tmp_path, PRSIM_BODY)
    with pytest.raises(raw_ingest.raw_staging.StagingError):
        _ingest_prsim(settings, pg, world, kb["key"], tree, accept=False)
    report = _ingest_prsim(settings, pg, world, kb["key"], tree, accept=True)
    assert report.outcomes == {"created": 1} and report.masked == {"EMAIL_ADDRESS": 1}
    assert report.manifest()["personnel_data_sources"] == ["jira:PRSIM"]
    text = " ".join(
        r[0] for r in pg.execute("SELECT text FROM chunks WHERE kb_id = %s", (kb["id"],))
    )
    assert "destek@example.test" not in text and "[EMAIL_ADDRESS]" in text


@pytest.mark.parametrize(
    "value", ["kart 4111 1111 1111 1111", "TC 10000000146", "IBAN TR33 0006 1005 1978 6457 8413 26"]
)
def test_19_s1_customer_data_in_personnel_source_stops(world, pg, settings, tmp_path, value):
    kb = create_kb(world, key=f"prsim-{uuid.uuid4().hex[:6]}")
    tree = _prsim_tree(tmp_path, PRSIM_BODY + f"\nNot: {value}\n")
    with pytest.raises(raw_ingest.RawIngestError) as err:
        _ingest_prsim(settings, pg, world, kb["key"], tree, accept=True)
    assert err.value.code == "customer_data_suspected"
    assert "PRSIM-1" in str(err.value) and "4111" not in str(err.value)


# --- r1 MAJOR-2: metadata strings are masked like the body; PRSIM scan covers them ---

META_PII = "destek@example.test"


def _one_doc_tree(tmp_path, source, meta_extra, body=PRSIM_BODY, name="DOC-1"):
    kind, space = source.split(":")
    tree = tmp_path / f"t-{uuid.uuid4().hex[:6]}"
    path = tree / kind / space / name / f"{name}.md"
    path.parent.mkdir(parents=True)
    path.write_text(body, encoding="utf-8")
    meta = {"source": source, "source_item_id": f"{kind}:{name}"} | meta_extra
    Path(f"{path}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return tree


def test_19_r1_metadata_strings_masked_everywhere(world, pg, settings, tmp_path):
    kb = create_kb(world, key=f"meta-{uuid.uuid4().hex[:6]}")
    tree = _one_doc_tree(
        tmp_path,
        "confluence:DEMO",
        {
            "title": f"Destek ({META_PII})",
            "breadcrumb": f"DEMO › İletişim {META_PII} › 0532 256 60 38",
            "source_url": f"https://wiki.example.test/x?mail={META_PII}",
        },
    )
    report = asyncio.run(
        raw_ingest.ingest_tree(
            text_filter="pii_regex",  # 19 measures the regex filter (08 tam 1b default pii_ner)
            project_key=_project_key(pg, world["project"]),
            kb_key=kb["key"],
            raw_dir=tree,
            acl_roles=["analyst"],
            sources=["confluence:DEMO"],
            limit=None,
            settings=settings,
            embed_client=ingest.LocalEmbedClient(settings),
            convert=convert_without_weights,
        )
    )
    assert report.masked["EMAIL_ADDRESS"] >= 4 and report.masked["TR_PHONE"] >= 1, report.lines()
    row = pg.execute(
        "SELECT breadcrumb, metadata::text, silver_path FROM documents WHERE kb_id = %s",
        (kb["id"],),
    ).fetchone()
    silver = Path(row[2]).read_text(encoding="utf-8")
    for text in (row[0], row[1], silver):
        assert META_PII not in text and "0532 256 60 38" not in text
    assert "[EMAIL_ADDRESS]" in row[0]
    hits = search(world["analyst"], world, kb["id"], "personel yetki talebi").json()["hits"]
    assert hits and all(META_PII not in h["breadcrumb"] for h in hits)


def test_19_r1_customer_data_in_prsim_title_stops(world, pg, settings, tmp_path):
    kb = create_kb(world, key=f"prsim-{uuid.uuid4().hex[:6]}")
    tree = _one_doc_tree(
        tmp_path, "jira:PRSIM", {"title": "PRSIM-9 kart 4111 1111 1111 1111"}, name="PRSIM-9"
    )
    with pytest.raises(raw_ingest.RawIngestError) as err:
        _ingest_prsim(settings, pg, world, kb["key"], tree, accept=True)
    assert err.value.code == "customer_data_suspected" and "4111" not in str(err.value)
    rows = pg.execute("SELECT count(*) FROM documents WHERE kb_id = %s", (kb["id"],)).fetchone()
    assert rows[0] == 0  # stopped before the document was registered


# --- r1 MINOR-5: undecodable personnel text is a coded refusal, the run goes on ---


def test_19_r1_invalid_encoding_refused_and_counted(world, pg, settings, tmp_path):
    kb = create_kb(world, key=f"prsim-{uuid.uuid4().hex[:6]}")
    tree = _one_doc_tree(tmp_path, "jira:PRSIM", {}, name="PRSIM-3")
    bad = tree / "jira" / "PRSIM" / "PRSIM-4" / "PRSIM-4.md"
    bad.parent.mkdir(parents=True)
    bad.write_bytes(b"\xff\xfe gecersiz \xc3\x28")
    Path(f"{bad}.meta.json").write_text(
        json.dumps({"source": "jira:PRSIM", "source_item_id": "jira:PRSIM-4"}), encoding="utf-8"
    )
    report = _ingest_prsim(settings, pg, world, kb["key"], tree, accept=True)
    assert report.rejected == {"invalid_encoding": 1}
    assert report.outcomes == {"created": 1}


# --- FOLLOWUP-155 (T-18k2-0005 B2): only an indexed document is `unchanged`; failed, gated and
# other unfinished documents are retried on the next run without a new version; an exception
# leaves the row `failed` with its code; the console status line is the database's. ---

FAILING = "confluence/DEMO/1002.md"


def _fail_one(path, filename, settings):
    if filename == FAILING:
        return failed("test", "docling_failed", "conversion failed in the test")
    return convert_without_weights(path, filename, settings)


class _RaisingEmbed:
    model = "never"

    async def embed(self, texts):
        raise RuntimeError("embedding service unreachable in the test")


def _rows(pg, kb_id):
    return {
        r[0]: (r[1], r[2], r[3])
        for r in pg.execute(
            "SELECT filename, status, version, metadata FROM documents WHERE kb_id = %s",
            (kb_id,),
        ).fetchall()
    }


def test_19r_155_rerun_retries_failed(world, pg, settings, ro_tree):
    kb = create_kb(world, key="paycore-retry")
    key = _project_key(pg, world["project"])
    first = _ingest(settings, key, kb["key"], ro_tree, convert=_fail_one)
    assert first.statuses == {"indexed": 3, "failed": 1, "skipped": 1}, first.lines()
    assert _rows(pg, kb["id"])[FAILING][0] == "failed"

    second = _ingest(settings, key, kb["key"], ro_tree)  # the cause is gone (e.g. make models)
    assert second.outcomes == {"unchanged": 4, "retried": 1}, second.lines()
    assert second.statuses == {"indexed": 1}, second.lines()
    rows = _rows(pg, kb["id"])
    assert rows[FAILING][0] == "indexed"
    assert {version for _, version, _ in rows.values()} == {1}  # a retry is not a new version


def test_19r_155_rerun_retries_gated_keeps_indexed(world, pg, settings, ro_tree):
    kb = create_kb(world, key="paycore-gated")
    key = _project_key(pg, world["project"])
    _ingest(settings, key, kb["key"], ro_tree)
    # A run that stopped between steps leaves the row in an intermediate status.
    pg.execute(
        "UPDATE documents SET status = 'gated' WHERE kb_id = %s AND filename = %s",
        (kb["id"], FAILING),
    )
    again = _ingest(settings, key, kb["key"], ro_tree)
    assert again.outcomes == {"unchanged": 4, "retried": 1}, again.lines()
    rows = _rows(pg, kb["id"])
    assert rows[FAILING][0] == "indexed"
    # indexed and skipped (a gate decision on the same bytes) are not retried
    assert sorted(status for status, _, _ in rows.values()) == ["indexed"] * 4 + ["skipped"]


def test_19r_155_exception_marks_failed(world, pg, settings, ro_tree):
    kb = create_kb(world, key="paycore-raise")
    key = _project_key(pg, world["project"])
    report = _ingest(settings, key, kb["key"], ro_tree, embed_client=_RaisingEmbed())
    rows = _rows(pg, kb["id"])
    stuck = {name: row for name, row in rows.items() if row[0] != "skipped"}
    assert stuck and all(status == "failed" for status, _, _ in stuck.values()), rows
    for _, _, meta in stuck.values():
        assert meta["error_code"] == "RuntimeError"  # the class name, never the message
        assert "unreachable" not in json.dumps(meta)
    assert report.manifest()["failed"] == len(stuck)
    assert report.statuses["failed"] == len(stuck)
    # the retry that succeeds leaves no stale code behind
    again = _ingest(settings, key, kb["key"], ro_tree)
    assert again.outcomes["retried"] == len(stuck), again.lines()
    for name in stuck:
        status, _, meta = _rows(pg, kb["id"])[name]
        assert status == "indexed" and "error_code" not in meta


def test_19r_155_console_statuses_match_manifest(world, pg, settings, ro_tree):
    kb = create_kb(world, key="paycore-console")
    key = _project_key(pg, world["project"])
    _ingest(settings, key, kb["key"], ro_tree, convert=_fail_one)
    # Same bytes, same failure: the second run retries and says so; the status line is the
    # database's (the manifest's), not this run's counter.
    report = _ingest(settings, key, kb["key"], ro_tree, convert=_fail_one)
    manifest = report.manifest()
    assert manifest["statuses"] == {"failed": 1, "indexed": 3, "skipped": 1}
    lines = report.lines()
    assert "status: failed 1, indexed 3, skipped 1" in lines, lines
    assert "retried 1" in lines and "unchanged 4" in lines, lines


# --- review r1 MAJOR-1/2 (K-19R-0013 A): an error before the document is registered is counted
# (`failed_unregistered`: source, raw path, error code; no content), the manifest's `failed` and
# the CLI exit code see it, no placeholder row is created, and an earlier indexed version of the
# same file is not touched (it stays in search). ---


def _writable_tree(tmp_path):
    target = tmp_path / "raw-rw"
    shutil.copytree(TREE, target)
    return target


def _break_meta(tree, rel, **changes):
    meta_path = tree / f"{rel}.meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta.update(changes)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")


def test_19r_r1m1_error_before_registration_counted(world, pg, settings, tmp_path):
    kb = create_kb(world, key="paycore-unreg")
    tree = _writable_tree(tmp_path)
    new = tree / "confluence" / "DEMO" / "9001.md"
    new.write_text("# Yeni sayfa\n\nKurulum adımları ve kontrol listesi.\n", encoding="utf-8")
    (tree / "confluence" / "DEMO" / "9001.md.meta.json").write_text(
        json.dumps({"source": "confluence:DEMO", "source_item_id": "9001"}), encoding="utf-8"
    )
    _break_meta(tree, "confluence/DEMO/9001.md", updated_at_source="not-a-date")
    report = _ingest(settings, _project_key(pg, world["project"]), kb["key"], tree)
    manifest = report.manifest()
    assert manifest["failed_unregistered"] == [
        {"source": "confluence:DEMO", "path": "confluence/DEMO/9001.md", "error_code": "ValueError"}
    ]
    assert manifest["failed"] == 1  # what the CLI exit code reads
    assert "failed_unregistered 1" in report.lines(), report.lines()
    assert "not-a-date" not in json.dumps(manifest)  # no content, only the code
    rows = _rows(pg, kb["id"])
    assert "confluence/DEMO/9001.md" not in rows  # no placeholder row
    assert sorted(s for s, _, _ in rows.values()) == ["indexed"] * 4 + ["skipped"]


def test_19r_r1m2_new_version_error_keeps_old_version_searchable(world, pg, settings, tmp_path):
    kb = create_kb(world, key="paycore-oldver")
    key = _project_key(pg, world["project"])
    tree = _writable_tree(tmp_path)
    _ingest(settings, key, kb["key"], tree)
    rel = "confluence/DEMO/1002.md"
    page = tree / rel
    page.write_text(page.read_text(encoding="utf-8") + "\nYeni paragraf.\n", encoding="utf-8")
    _break_meta(tree, rel, updated_at_source="not-a-date")
    report = _ingest(settings, key, kb["key"], tree)
    assert [e["path"] for e in report.manifest()["failed_unregistered"]] == [rel]
    status, version, meta = _rows(pg, kb["id"])[rel]
    assert (status, version) == ("indexed", 1) and "error_code" not in meta
    response = search(world["analyst"], world, kb["id"], "fesih bildirim süresi kaç gün")
    assert response.status_code == 200, response.text
    assert any(h["document_name"] == rel for h in response.json()["hits"])
