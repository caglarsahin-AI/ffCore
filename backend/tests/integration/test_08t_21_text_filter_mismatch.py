"""08 tam 1b r1 MAJOR-3: a record ingested under another text filter is never processed again by a
run of a different filter; it is refused as `text_filter_mismatch`, counted, and the manifest
gives the real distribution of filters (documents and chunks per filter label).

Before: a `pii_ner` run counted `pii_regex@1` records as `unchanged` under its own label and
retried a failed one with its recorded `pii_regex` filter: a PRSIM record from the M3 mode was
written with names unmasked by a run whose manifest said `pii_ner@1`.
"""

import asyncio

from ffcore.guardrails.findings import Finding
from ffcore.knowledge import ingest, ingest_mask, raw_ingest
from tests.converters import convert_without_weights
from tests.integration.test_04a_api import create_kb, queue, settings, world
from tests.integration.test_19_ingest_raw import (
    PRSIM_BODY,
    SOURCES,
    _project_key,
    _prsim_tree,
    _rows,
    ro_tree,
)

__all__ = ["queue", "ro_tree", "settings", "world"]  # fixtures used by name below


class FakeNer:
    model, revision = "acme/turkish-ner", "0123456789abcdef"

    async def find(self, text, categories):
        start = text.find("Ayşe Demir")
        return (
            [] if start == -1 else [Finding("PERSON", start, start + 10, 0.97, "ner", "Ayşe Demir")]
        )


def _run(settings, pg, world, kb_key, tree, *, sources, text_filter, accept=False, convert=None):
    return asyncio.run(
        raw_ingest.ingest_tree(
            project_key=_project_key(pg, world["project"]),
            kb_key=kb_key,
            raw_dir=tree,
            acl_roles=["analyst"],
            sources=sources,
            limit=None,
            settings=settings,
            embed_client=ingest.LocalEmbedClient(settings),
            convert=convert or convert_without_weights,
            accept_personnel_data=accept,
            text_filter=text_filter,
        )
    )


def test_08t_21_prsim_m3_failed_record_not_retried_by_pii_ner(
    world, pg, settings, tmp_path, monkeypatch
):
    monkeypatch.setattr(ingest_mask, "ner_client", lambda: FakeNer())
    kb = create_kb(world, key="prsim-mismatch")
    tree = _prsim_tree(tmp_path, PRSIM_BODY + "\nTalep sahibi Ayşe Demir.\n")
    calls = []

    def failing(path, filename, s):
        calls.append(filename)
        raise RuntimeError("conversion failed in the test")

    m3 = _run(
        settings,
        pg,
        world,
        kb["key"],
        tree,
        sources=["jira:PRSIM"],
        text_filter="pii_regex",
        accept=True,
        convert=failing,
    )
    assert m3.statuses == {"failed": 1}, m3.lines()
    calls.clear()

    def recording(path, filename, s):
        calls.append(filename)
        return convert_without_weights(path, filename, s)

    report = _run(
        settings,
        pg,
        world,
        kb["key"],
        tree,
        sources=["jira:PRSIM"],
        text_filter="pii_ner",
        convert=recording,
    )
    assert calls == []  # never converted again, never written with names unmasked
    assert "retried" not in report.outcomes, report.lines()
    manifest = report.manifest()
    assert manifest["text_filter"] == "pii_ner@1"
    assert manifest["text_filter_mismatch"] == 1
    assert manifest["text_filters"] == {"pii_regex@1": {"documents": 1, "chunks": 0}}
    ((status, _, meta),) = _rows(pg, kb["id"]).values()
    assert status == "failed" and meta["text_filter"] == "pii_regex@1"
    assert any("text_filter_mismatch 1" in line for line in report.lines()), report.lines()


def test_08t_21b_indexed_regex_records_are_not_unchanged_under_pii_ner(
    world, pg, settings, ro_tree, monkeypatch
):
    monkeypatch.setattr(ingest_mask, "ner_client", lambda: FakeNer())
    kb = create_kb(world, key="regex-then-ner")
    first = _run(settings, pg, world, kb["key"], ro_tree, sources=SOURCES, text_filter="pii_regex")
    regex = first.manifest()
    assert regex["text_filters"] == {
        "pii_regex@1": {"documents": regex["documents"], "chunks": regex["chunks"]}
    }
    assert regex["text_filter_mismatch"] == 0

    again = _run(settings, pg, world, kb["key"], ro_tree, sources=SOURCES, text_filter="pii_ner")
    assert "unchanged" not in again.outcomes, again.lines()
    manifest = again.manifest()
    assert manifest["text_filter_mismatch"] == regex["documents"]
    # the real distribution: every document still carries the filter it was written with
    assert manifest["text_filters"] == regex["text_filters"]
