"""13b acceptance 7: `make eval`'s scoring and report (scripts/eval_report.py), without a stack.
The runner's HTTP part is proven by the stacked `make eval` run (state/pr/13b-a.md)."""

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("eval_report", REPO / "scripts" / "eval_report.py")
er = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(er)

DOC = {
    "id": "q01",
    "input": {"message": "Fesih bildirim süresi kaç gündür?", "variables": {}},
    "expected_output": {"must_contain": ["90 gün"], "must_cite": ["SZL-2024-011_cihaz-bakim.pdf"]},
    "metadata": {"answerable": True, "style": "dogrudan", "tags": ["belge"]},
}
NONE = {
    "id": "q21",
    "input": {"message": "Otopark ücreti nedir?", "variables": {}},
    "expected_output": {"must_contain": []},
    "metadata": {"answerable": False, "style": "alan_disi_cevapsiz", "tags": []},
}
SQL = {
    "id": "q29",
    "input": {"message": "Kaç yatak var?", "variables": {}},
    "expected_output": {"must_contain": ["18"], "sql_result": [[18]]},
    "metadata": {"answerable": True, "style": "dogrudan", "tags": ["sql"]},
}


def _sources(*names):
    return {"type": "sources", "payload": {"selected": [{"document_name": n} for n in names]}}


def test_13b_7_scorers_document_question():
    run = {
        "status": "completed",
        "output": "Süre 90 GÜN olarak yazılı.",
        "outcome_label": "answered",
    }
    # the seed uploads DOCX as <stem>.txt: a source matches its expected document by stem
    events = [_sources("SZL-2024-011_cihaz-bakim.txt"), {"type": "llm_call", "payload": {}}]
    scores = er.score(DOC, run, events)
    assert scores == {"contains": True, "cites_source": True, "llm_judge": None}
    assert er.passed(scores) is True
    wrong = er.score(DOC, {**run, "output": "30 gün"}, [_sources("other.pdf")])
    assert wrong["contains"] is False and wrong["cites_source"] is False


def test_13b_7_scorers_unanswerable_holds_only_without_an_answer():
    held = er.score(NONE, {"status": "completed", "output": "", "outcome_label": "declined"}, [])
    assert held["holds"] is True
    made_up = er.score(
        NONE, {"status": "completed", "output": "50 TL", "outcome_label": "answered"}, []
    )
    assert made_up["holds"] is False


def test_13b_7_scorers_sql_result_from_the_tool_result():
    events = [{"type": "tool_result", "payload": {"name": "mcp-sql__run_sql", "result": "[[18]]"}}]
    ok = er.score(
        SQL, {"status": "completed", "output": "18 yatak", "outcome_label": "answered"}, events
    )
    assert ok["sql_result"] is True and ok["contains"] is True
    miss = er.score(SQL, {"status": "completed", "output": "18", "outcome_label": "answered"}, [])
    assert miss["sql_result"] is False  # the number in the text alone is not a SQL result


def test_13b_7_failed_run_fails_every_scorer():
    scores = er.score(DOC, {"status": "failed", "output": None, "error_code": "x"}, [])
    assert scores["contains"] is False and er.passed(scores) is False


def test_13b_7_report_shape():
    results = [
        er.ItemResult(
            "q01",
            "dogrudan",
            True,
            False,
            "answered",
            "completed",
            {"contains": True, "cites_source": True, "llm_judge": None},
            12.0,
            1,
        ),
        er.ItemResult(
            "q21",
            "alan_disi_cevapsiz",
            False,
            False,
            "declined",
            "completed",
            {"holds": True, "llm_judge": None},
            3.0,
            0,
        ),
        er.ItemResult(
            "q29",
            "dogrudan",
            True,
            True,
            None,
            "not_run",
            {},
            None,
            0,
            "NOT_RUN: --approve-sql not given",
        ),
    ]
    text = er.markdown(
        {"dataset": "sozlesme-33", "agent": "sozlesme-asistani", "model": "fake-llm"}, results
    )
    assert "fake-llm" in text and "not a measurement" in text  # a fake model is never a result
    assert "| answered | 1 |" in text and "| declined | 1 |" in text
    assert "Document questions with the right source: 1/1" in text
    assert "Unanswerable questions held: 1/1" in text
    assert "SQL questions: 0/0 (1 NOT_RUN" in text
    assert "llm_judge: NOT_RUN" in text
    assert "| q29 |" in text and "--approve-sql" in text
