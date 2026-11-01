"""19: `ingest-raw` end to end on the synthetic PayCore-like tree (plan/19 kabul 1, şart 1-2).

The tree is copied to a read-only directory first: the command must work on a `:ro` mount and
write nothing under it. Raw bytes are unchanged; silver, text_raw and chunks are masked.
"""

import asyncio
import hashlib
import os
import shutil
import stat
from pathlib import Path

import pytest

from ffcore.knowledge import ingest, ingest_mask, raw_ingest
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
            project_key=project_key,
            kb_key=kb_key,
            raw_dir=tree,
            acl_roles=["analyst"],
            sources=kw.pop("sources", SOURCES),
            limit=kw.pop("limit", None),
            settings=settings,
            embed_client=ingest.LocalEmbedClient(settings),
            convert=convert_without_weights,
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
