"""Reviewer probes for package 19 (ffcore side): ingest-raw boundary. Copied into
backend/tests/integration/ of the review worktree and removed afterwards."""
import asyncio
import hashlib
import json
import os
import shutil
from pathlib import Path

import pytest

from ffcore.knowledge import ingest, raw_ingest, raw_staging
from tests.converters import convert_without_weights
from tests.integration.test_04a_api import create_kb, queue, settings, world  # noqa: F401

CARD, IBAN, TCKN = "4111111111111111", "TR330006100519786457841326", "10000000146"
EMAIL, PHONE = "ali.veli@example.org", "0532 256 60 38"


def put(base: Path, rel: str, text: str, source: str, item: str, **meta):
    path = base / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    m = {"source": source, "source_item_id": item, **meta}
    Path(f"{path}.meta.json").write_text(json.dumps(m), encoding="utf-8")
    return path


def snapshot(tree: Path):
    return sorted((str(p.relative_to(tree)), hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "dir")
                  for p in tree.rglob("*"))


def project_key(pg, world):
    return pg.execute("SELECT key FROM projects WHERE id = %s", (world["project"],)).fetchone()[0]


def ingest_tree(settings, pg, world, kb_key, tree, sources, **kw):
    return asyncio.run(raw_ingest.ingest_tree(
        project_key=project_key(pg, world), kb_key=kb_key, raw_dir=tree, acl_roles=["analyst"],
        sources=sources, limit=None, settings=settings, embed_client=ingest.LocalEmbedClient(settings),
        convert=convert_without_weights, **kw))


def test_p1_paths_symlinks_traversal(tmp_path, pg, world, settings):
    outside = tmp_path / "outside"; outside.mkdir(); (outside / "secret.md").write_text("TOP-SECRET-OUTSIDE " + EMAIL)
    tree = tmp_path / "raw"
    put(tree, "confluence/DEMO/ok.md", "# ok\n\nfine text here for the test.\n", "confluence:DEMO", "1")
    # symlinked document
    os.symlink(outside / "secret.md", tree / "confluence/DEMO/link.md")
    Path(f"{tree}/confluence/DEMO/link.md.meta.json").write_text(json.dumps({"source": "confluence:DEMO", "source_item_id": "2"}))
    # symlinked directory
    os.symlink(outside, tree / "confluence/LINKDIR")
    # attachment traversal / symlink / absolute
    for i, att in enumerate(["../../../outside/secret.md", "/etc/passwd", "link.md", "sub/x.md"]):
        put(tree, f"confluence/DEMO/att{i}.md", "# a\n\ntext\n", "confluence:DEMO", f"a{i}", attachments=[att])
    # symlinked meta file
    p = put(tree, "confluence/DEMO/metalink.md", "# m\n\ntext\n", "confluence:DEMO", "9")
    Path(f"{p}.meta.json").unlink(); os.symlink(outside / "secret.md", Path(f"{p}.meta.json"))
    kb = create_kb(world, key="p1")
    before = snapshot(tree)
    items = list(raw_staging.iter_staged(tree, ["confluence:DEMO"]))
    accepted = [i.relpath for i in items if isinstance(i, raw_staging.StagedItem)]
    rejected = {(i.relpath, i.code) for i in items if isinstance(i, raw_staging.Rejected)}
    print("P1 accepted:", accepted); print("P1 rejected:", sorted(rejected))
    assert accepted == ["confluence/DEMO/ok.md"]
    assert not any("secret" in a for a in accepted)
    report = ingest_tree(settings, pg, world, kb["key"], tree, ["confluence:DEMO"])
    assert snapshot(tree) == before
    rows = pg.execute("SELECT filename FROM documents WHERE kb_id = %s", (kb["id"],)).fetchall()
    assert [r[0] for r in rows] == ["confluence/DEMO/ok.md"]
    chunks = " ".join(r[0] for r in pg.execute("SELECT text FROM chunks WHERE kb_id=%s", (kb["id"],)))
    assert "TOP-SECRET-OUTSIDE" not in chunks
    print("P1 report:", report.lines()[:5])


def test_p2_prsim_variants_without_flag(tmp_path):
    tree = tmp_path / "raw"
    variants = {
        "exact": ("jira:PRSIM", "jira/PRSIM/a.txt"),
        "lower": ("jira:prsim", "jira/PRSIM/b.txt"),
        "spaces": (" jira:PRSIM ", "jira/PRSIM/c.txt"),
        "bare": ("PRSIM", "jira/PRSIM/d.txt"),
        "suffix": ("jira:PRSIM2", "jira/PRSIM/e.txt"),
        "dash": ("confluence:PRSIM-DOCS", "confluence/PRSIM-DOCS/f.txt"),
        "path_vs_source": ("jira:DEMO", "jira/PRSIM/g.txt"),   # mapper puts a PRSIM file under another source
        "case_path": ("jira:DEMO", "jira/prsim/h.txt"),
    }
    for name, (src, rel) in variants.items():
        put(tree, rel, "text body " + name, src.strip() if name == "spaces" else src, name)
    got = {}
    for name, (src, rel) in variants.items():
        try:
            items = list(raw_staging.iter_staged(tree, [src.strip()]))
            hit = [i for i in items if getattr(i, "relpath", None) == rel or (isinstance(i, raw_staging.Rejected) and i.relpath == rel)]
            got[name] = ("accepted" if any(isinstance(i, raw_staging.StagedItem) for i in hit) else
                         ",".join(i.code for i in hit if isinstance(i, raw_staging.Rejected)) or "none")
        except raw_staging.StagingError as e:
            got[name] = f"refused:{e.code}"
    print("P2", got)
    assert got["exact"].endswith("prsim_requires_ner") and got["lower"].endswith("prsim_requires_ner")
    assert got["spaces"].endswith("prsim_requires_ner") and got["bare"].endswith("prsim_requires_ner")
    # informational: not asserted — reported as findings if accepted
    print("P2 INFO suffix/dash/path_vs_source/case_path:", got["suffix"], got["dash"], got["path_vs_source"], got["case_path"])


def test_p3_metadata_fields_are_not_masked(tmp_path, pg, world, settings):
    tree = tmp_path / "raw"
    put(tree, "confluence/DEMO/m.md", "# page\n\nplain body without identifiers, long enough to chunk.\n",
        "confluence:DEMO", "m1", title=f"Contact {EMAIL}", breadcrumb=f"DEMO › {EMAIL} › {PHONE}",
        source_url=f"https://wiki.example.test/x?mail={EMAIL}", updated_at_source="2026-01-01T00:00:00Z",
        author="Ali Veli", assignee="Zeynep K")
    kb = create_kb(world, key="p3")
    ingest_tree(settings, pg, world, kb["key"], tree, ["confluence:DEMO"])
    doc = pg.execute("SELECT id, breadcrumb, metadata, silver_path FROM documents WHERE kb_id=%s", (kb["id"],)).fetchone()
    chunks = [r for r in pg.execute("SELECT text, breadcrumb FROM chunks WHERE kb_id=%s", (kb["id"],))]
    silver = Path(doc[3]).read_text(encoding="utf-8")
    blob = {"document.breadcrumb": doc[1], "document.metadata": json.dumps(doc[2]), "silver": silver,
            "chunks": json.dumps(chunks, default=str)}
    leaks = {k: (EMAIL in v, PHONE in v) for k, v in blob.items()}
    print("P3 raw email/phone present in:", leaks)
    assert "author" not in json.dumps(doc[2]) and "Ali Veli" not in json.dumps(doc[2])  # unknown meta never copied
    # the finding, if any, is printed above; hard assertions are in the report


def test_p4_customer_data_stops_prsim(tmp_path, pg, world, settings):
    tree = tmp_path / "raw"
    put(tree, "jira/PRSIM/PRSIM-9.txt", f"Issue about staff access. card {CARD} must not be here.\n", "jira:PRSIM", "jira:PRSIM-9")
    put(tree, "jira/PRSIM/PRSIM-8.txt", f"iban {IBAN} in text.\n", "jira:PRSIM", "jira:PRSIM-8")
    put(tree, "jira/PRSIM/PRSIM-7.txt", f"id {TCKN} in text.\n", "jira:PRSIM", "jira:PRSIM-7")
    put(tree, "jira/PRSIM/PRSIM-1.txt", f"staff mail {EMAIL} phone {PHONE} only.\n", "jira:PRSIM", "jira:PRSIM-1")
    kb = create_kb(world, key="p4")
    for stem in ("PRSIM-9", "PRSIM-8", "PRSIM-7"):
        only = tmp_path / f"only-{stem}"; only.mkdir()
        shutil.copytree(tree / "jira", only / "jira", ignore=shutil.ignore_patterns(*(f"PRSIM-{n}*" for n in (9, 8, 7, 1) if f"PRSIM-{n}" != stem)))
        with pytest.raises(raw_ingest.RawIngestError) as e:
            ingest_tree(settings, pg, world, kb["key"], only, ["jira:PRSIM"], accept_personnel_data=True)
        assert e.value.code == "customer_data_suspected"
        msg = str(e.value)
        assert CARD not in msg and IBAN not in msg and TCKN not in msg
        print("P4", stem, "->", msg[:160])
    # staff-only data passes and is masked
    ok = tmp_path / "ok"; shutil.copytree(tree / "jira", ok / "jira", ignore=shutil.ignore_patterns("PRSIM-9*", "PRSIM-8*", "PRSIM-7*"))
    report = ingest_tree(settings, pg, world, kb["key"], ok, ["jira:PRSIM"], accept_personnel_data=True)
    assert report.outcomes["created"] == 1 and report.personnel_data_sources == {"jira:PRSIM"}
    chunks = " ".join(r[0] for r in pg.execute("SELECT text FROM chunks WHERE kb_id=%s", (kb["id"],)))
    assert EMAIL not in chunks and PHONE not in chunks
    # and without the flag the same tree is refused before any DB work
    with pytest.raises(raw_staging.StagingError) as e:
        ingest_tree(settings, pg, world, kb["key"], ok, ["jira:PRSIM"])
    assert e.value.code == "prsim_requires_ner"
    # data already inside the documents table for PRSIM-9/8/7? (stopped before register)
    n = pg.execute("SELECT count(*) FROM documents WHERE kb_id=%s AND filename LIKE %s", (kb["id"], "%PRSIM-9%")).fetchone()[0]
    print("P4 documents rows for the card file:", n)


def test_p5_unknown_text_filter_never_passes_through(tmp_path, pg, world, settings):
    with pytest.raises(ValueError):
        from ffcore.knowledge import ingest_mask
        ingest_mask.resolve("nope")
    tree = tmp_path / "raw"
    p = put(tree, "confluence/DEMO/f.md", f"# f\n\nmail {EMAIL} text text text.\n", "confluence:DEMO", "f1")
    kb = create_kb(world, key="p5")
    with pytest.raises(ValueError):
        asyncio.run(ingest.ingest_from_raw(
            str(p), raw_staging.metadata_for(next(i for i in raw_staging.iter_staged(tree, ["confluence:DEMO"])), kb_id=kb["id"]),
            {"roles": ["analyst"]}, settings=settings, store=raw_ingest.get_vector_store(settings),
            embed_client=ingest.LocalEmbedClient(settings), convert=convert_without_weights, text_filter="nope"))
    n = pg.execute("SELECT count(*) FROM documents WHERE kb_id=%s", (kb["id"],)).fetchone()[0]
    assert n == 0, "no document registered for an unknown filter"


def test_p6_manifest_outside_raw_and_acl_required(tmp_path, pg, world, settings):
    tree = tmp_path / "raw"; put(tree, "confluence/DEMO/a.md", "# a\n\ntext text text.\n", "confluence:DEMO", "1")
    kb = create_kb(world, key="p6")
    report = ingest_tree(settings, pg, world, kb["key"], tree, ["confluence:DEMO"])
    with pytest.raises(raw_ingest.RawIngestError) as e:
        raw_ingest.write_manifest(report, tree / "m.json", raw_dir=tree)
    assert e.value.code == "manifest_inside_raw_dir"
    with pytest.raises(raw_ingest.RawIngestError) as e2:
        asyncio.run(raw_ingest.ingest_tree(project_key=project_key(pg, world), kb_key=kb["key"], raw_dir=tree,
                                           acl_roles=[], sources=["confluence:DEMO"], limit=None, settings=settings))
    assert e2.value.code == "acl_required"
    with pytest.raises(raw_staging.StagingError) as e3:
        list(raw_staging.iter_staged(tree, []))
    assert e3.value.code == "sources_required"
