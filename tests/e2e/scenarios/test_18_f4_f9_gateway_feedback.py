"""F4 (managed LLM gateway: no raw PII reaches the provider, trace chain) and F9 (expert review
queue), plan/18."""

import json

import pytest

from .conftest import load

PROJECT = "hastane-a"


def _pii_samples(n: int = 5) -> list[tuple[str, list[str]]]:
    """Sentences from the 13a PII set with only categories 08-lite masks by default, and the
    raw values that must not leave."""
    out = []
    for row in load("pii/pii-100.jsonl"):
        cats = {e["category"] for e in row["entities"]}
        if cats and cats <= {"TR_NATIONAL_ID", "TR_PHONE", "TR_IBAN", "EMAIL_ADDRESS"}:
            out.append((row["text"], [row["text"][e["start"] : e["end"]] for e in row["entities"]]))
        if len(out) == n:
            break
    return out


def test_18_f4_1_provider_never_sees_raw_pii(login, fake_llm):
    analyst = login(PROJECT, "analyst", "edit")
    pid = analyst.project_id(PROJECT)
    fake_llm.reset()
    for text, _ in _pii_samples():
        run = analyst.settle(pid, analyst.start_run(pid, "sozlesme-asistani", text))
        assert run.detail["status"] in ("completed", "failed"), run.detail
    bodies = json.dumps(fake_llm.requests(), ensure_ascii=False)
    assert bodies != "[]", "the fake provider saw no request; is the agent's model on fake-llm?"
    for _, values in _pii_samples():
        for v in values:
            assert v not in bodies, f"raw PII reached the provider: {v[:4]}…"


def test_18_f4_2_trace_chain(login):
    """run → Langfuse trace, and the masked request the model got is on the llm_call event."""
    analyst = login(PROJECT, "analyst", "edit")
    pid = analyst.project_id(PROJECT)
    run = analyst.settle(pid, analyst.start_run(pid, "sozlesme-asistani", "Merhaba"))
    assert run.detail.get("langfuse_trace_id"), run.detail
    calls = [e for e in analyst.run_events(pid, run.id) if e["type"] == "llm_call"]
    assert calls and all(c["payload"].get("request_messages") for c in calls), calls


def test_18_f4_2b_litellm_call_id_in_run_events(login):
    """run → LiteLLM call id (K-06a-0007: additive `litellm_call_id` on every llm_call event;
    null only when LiteLLM gave none, never missing)."""
    analyst = login(PROJECT, "analyst", "edit")
    pid = analyst.project_id(PROJECT)
    run = analyst.settle(pid, analyst.start_run(pid, "sozlesme-asistani", "Merhaba"))
    calls = [e for e in analyst.run_events(pid, run.id) if e["type"] == "llm_call"]
    assert calls and all("litellm_call_id" in c["payload"] for c in calls), calls
    # Through LiteLLM to fake-llm the id is expected to be set; null is reported, not hidden.
    assert all(c["payload"]["litellm_call_id"] for c in calls), [c["payload"] for c in calls]


def test_18_f4_3_quota_429():
    pytest.skip("NOT_RUN: quotas are package 03c (PoC sonrası)")


def test_18_f4_4_tool_arguments_masked():
    """08-lite masks PII in tool arguments at tool.pre (06a review MAJOR-2)."""
    pytest.skip("NOT_RUN: gerçek model gerekir (the model must call a tool with the value)")


def test_18_f9_1_feedback_and_pending_view(login):
    editor = login(PROJECT, "analyst", "edit")
    pid = editor.project_id(PROJECT)
    run = editor.settle(pid, editor.start_run(pid, "sozlesme-asistani", "Merhaba"))
    pending = editor.get(f"/api/v1/projects/{pid}/runs", params={"feedback": "pending"}).json()
    assert run.id in {r["id"] for r in pending["items"]}
    r = editor.post(
        f"/api/v1/projects/{pid}/runs/{run.id}/feedback", json={"vote": "partial", "note": "e2e"}
    )
    assert r.status_code == 200, r.text
    pending = editor.get(f"/api/v1/projects/{pid}/runs", params={"feedback": "pending"}).json()
    assert run.id not in {r["id"] for r in pending["items"]}


def test_18_f9_2_read_only_cannot_review(login):
    editor = login(PROJECT, "analyst", "edit")
    reader = login(PROJECT, "admin", "read")
    pid = editor.project_id(PROJECT)
    run = editor.settle(pid, editor.start_run(pid, "sozlesme-asistani", "Merhaba"))
    r = reader.post(f"/api/v1/projects/{pid}/runs/{run.id}/feedback", json={"vote": "correct"})
    assert r.status_code == 403, r.text
    assert r.json()["error"]["code"] == "read_only_access"


def test_18_f9_3_dataset_automation():
    pytest.skip("NOT_RUN: corrected answers into a dataset is package 09 (PoC sonrası)")
