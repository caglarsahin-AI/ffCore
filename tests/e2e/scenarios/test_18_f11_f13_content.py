"""F11 (poisoned documents and tickets) and F13 (document freshness), plan/18.

Both need their documents indexed in a knowledge base of their own (13b seed: `zehirli`,
`surumler`), so the F1 exam's KB is not affected.
"""

import pytest

from .conftest import load

PROJECT = "hastane-a"
DOCS = load("poison/expected.json")["documents"]


@pytest.mark.parametrize("case", DOCS, ids=lambda d: d["id"])
def test_18_f11_6_document_instruction_not_followed(login, case):
    analyst = login(PROJECT, "analyst", "edit")
    pid = analyst.project_id(PROJECT)
    run = analyst.settle(pid, analyst.start_run(pid, "zehirli-belge-asistani", case["question"]))
    answer = run.detail.get("output") or ""
    for needle in case["must_not_contain"]:
        assert needle not in answer, (case["id"], needle)
    for fact in case["must_contain"]:
        assert fact in answer, (case["id"], fact)
    called = {
        e["payload"].get("name")
        for e in analyst.run_events(pid, run.id)
        if e["type"] == "tool_call"
    }
    assert not (called & set(case["forbidden_tools"])), (case["id"], called)


def test_18_f11_7_ticket_instruction_not_followed():
    pytest.skip("NOT_RUN: needs ticket-desk (after 05a) and 07 approvals")


def test_18_f11_8_injection_recognizer_event():
    pytest.skip("NOT_RUN: injection recognizer is 08 full (plan/18 F11)")


@pytest.mark.parametrize("case", load("versions/expected.json"), ids=lambda v: v["code"])
def test_18_f13_4_answer_from_v2_with_date(login, case):
    analyst = login(PROJECT, "analyst", "edit")
    pid = analyst.project_id(PROJECT)
    run = analyst.settle(pid, analyst.start_run(pid, "surum-asistani", case["question"]))
    answer = run.detail.get("output") or ""
    for needle in case["must_contain"]:
        assert needle in answer, (case["code"], needle, answer[:200])
