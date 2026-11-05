"""08 tam 1b r2 NOTE-5 (KARARLAR "08 tam 1b r2 ekleri"): a personnel-data record written with
`pii_regex` in the M3 mode is inside the M3 boundary for reindex too.

`make reindex LAYER=silver` without `--accept-personnel-data` refuses with `prsim_requires_ner`
before it touches any document when such a record is in scope; with the flag it runs. The check
is the job's (`reindex_silver`), so the CLI and the API `reindex` endpoint take the same road;
the CLI checks before queueing and exits 2 with the code.
"""

import asyncio
import uuid

import pytest

from ffcore import cli
from ffcore.knowledge import ingest
from ffcore.knowledge.jobs import get_vector_store
from tests.converters import convert_without_weights
from tests.integration.conftest import audit_rows
from tests.integration.test_04a_api import create_kb, kb_url, queue, settings, world
from tests.integration.test_08t_21_text_filter_mismatch import _run
from tests.integration.test_19_ingest_raw import PRSIM_BODY, _project_key, _prsim_tree, _rows

__all__ = ["queue", "settings", "world"]  # fixtures used by name below


def _failing(path, filename, s):
    raise RuntimeError("conversion failed in the test")


def _m3_failed_prsim(world, pg, settings, tmp_path, key):
    kb = create_kb(world, key=key)
    tree = _prsim_tree(tmp_path, PRSIM_BODY + "\nTalep sahibi Ayşe Demir.\n")
    report = _run(
        settings,
        pg,
        world,
        kb["key"],
        tree,
        sources=["jira:PRSIM"],
        text_filter="pii_regex",
        accept=True,
        convert=_failing,
    )
    assert report.statuses == {"failed": 1}, report.lines()
    return kb


def _reindex(settings, kb, calls, **kw):
    def recording(path, filename, s):
        calls.append(filename)
        return convert_without_weights(path, filename, s)

    return asyncio.run(
        ingest.reindex_silver(
            uuid.UUID(str(kb["id"])),
            full=False,
            settings=settings,
            store=get_vector_store(settings),
            embed_client=ingest.LocalEmbedClient(settings),
            convert=recording,
            **kw,
        )
    )


def test_08t_30_reindex_refuses_m3_prsim_record_without_flag(world, pg, settings, tmp_path):
    kb = _m3_failed_prsim(world, pg, settings, tmp_path, "prsim-reindex")
    calls: list[str] = []
    with pytest.raises(ingest.ReindexRefused) as refused:
        _reindex(settings, kb, calls)
    assert refused.value.code == "prsim_requires_ner"
    assert calls == []  # no document touched
    ((status, _, meta),) = _rows(pg, kb["id"]).values()
    assert status == "failed" and meta["text_filter"] == "pii_regex@1"

    report = _reindex(settings, kb, calls, accept_personnel_data=True)
    assert report.documents == 1 and len(calls) == 1


def test_08t_30b_cli_reindex_exits_2_with_the_code(world, pg, settings, tmp_path, capsys):
    kb = _m3_failed_prsim(world, pg, settings, tmp_path, "prsim-reindex-cli")
    code = cli.main(
        [
            "reindex",
            "--project",
            _project_key(pg, world["project"]),
            "--kb",
            kb["key"],
            "--layer",
            "silver",
        ]
    )
    assert code == 2
    assert "prsim_requires_ner" in capsys.readouterr().err


def test_08t1c_3_reindex_api_409_prsim(world, pg, settings, queue, tmp_path):
    """FOLLOWUP-172 N1: the API refuses at the endpoint (409) instead of a 202 whose job fails;
    nothing is queued, the attempt is audited, and the job keeps its own check."""
    kb = _m3_failed_prsim(world, pg, settings, tmp_path, "prsim-reindex-api")
    response = world["analyst"].post(
        f"{kb_url(world, kb['id'])}/reindex", json={"layer": "silver", "full": False}
    )
    assert response.status_code == 409, response.text
    error = response.json()["error"]
    assert error["type"] == "conflict_error" and error["code"] == "prsim_requires_ner"
    assert "Ayşe" not in response.text  # the path and the code, never content
    assert queue.jobs == []
    rows = audit_rows(pg, "reindex_knowledge_base", project=world["project"])
    assert [outcome for _, outcome, _ in rows] == ["error"]


def test_08t1c_3b_reindex_api_ok_without_personnel(world, pg, settings, queue, tmp_path):
    """The early check does not block what it does not concern: gold, and silver with no
    personnel-data record in scope, are queued as before."""
    kb = _m3_failed_prsim(world, pg, settings, tmp_path, "prsim-reindex-api-gold")
    gold = world["analyst"].post(
        f"{kb_url(world, kb['id'])}/reindex", json={"layer": "gold", "full": True}
    )
    assert gold.status_code == 202, gold.text
    plain = create_kb(world, key="plain-reindex-api")
    silver = world["analyst"].post(
        f"{kb_url(world, plain['id'])}/reindex", json={"layer": "silver", "full": True}
    )
    assert silver.status_code == 202, silver.text
    assert queue.jobs == [
        ("reindex_job", kb["id"], "gold", True),
        ("reindex_job", plain["id"], "silver", True),
    ]
