"""F10 (project isolation and audit trail), plan/18 stage 2: a member of project B sees none of
project A's resources, by listing or by an id taken from A; and one run of A can be followed to
its LiteLLM call and its Langfuse trace (data/samples/projects/projects.json)."""

import json
import os
import time
import uuid

import httpx
import pytest

from .conftest import load

TRACE_WAIT_S = 60
INDEX_TERMINAL = ("indexed", "failed", "skipped", "timeout")


def _procedure(word: str) -> str:
    """A short procedure long enough for the ingest gates (a one-liner is skipped)."""
    lines = [
        f"{word} kayıt prosedürü",
        f"Madde 1 - Amaç: Bu prosedür {word} kayıtlarının nasıl tutulacağını açıklar.",
        f"Madde 2 - Süre: {word} kayıtları 30 gün boyunca saklanır, sonra arşive taşınır.",
        "Madde 3 - Sorumluluk: Kayıtların doğruluğundan birim sorumlusu sorumludur.",
        "Madde 4 - Erişim: Kayıtları yalnız yetkili personel görüntüleyebilir.",
    ]
    return "\n\n".join(lines * 3)


@pytest.fixture(scope="module")
def pair(seed, login):
    iso = seed["isolation"]
    owner = login(iso["target_project"], "admin", "edit")
    outsider = login(iso["viewer_project"], "admin", "edit")
    return iso, owner, owner.project_id(iso["target_project"]), outsider


@pytest.fixture(scope="module")
def a_run(pair):
    _, owner, a_pid, _ = pair
    # a question the contracts answer: without sources the run ends before any model call
    item = next(i for i in load("eval/sozlesme-33.json") if i["metadata"]["answerable"])
    return owner.settle(
        a_pid, owner.start_run(a_pid, "sozlesme-asistani", item["input"]["message"])
    )


def test_18_f10_4_direct_ids_are_404(pair, a_run):
    """Every A resource, by list and by an id taken from A, is a 404 for B's admin (no 403:
    the resource's existence does not leak), with nothing about A in the body."""
    iso, owner, a_pid, outsider = pair
    kb = owner.kb_id(a_pid, "sozlesmeler")
    tool = owner.tool_id(a_pid, "mcp-sql")
    docs = owner.get(f"/api/v1/projects/{a_pid}/knowledge-bases/{kb}/documents").json()["data"]
    base = f"/api/v1/projects/{a_pid}"
    reads = [
        f"{base}/knowledge-bases",
        f"{base}/knowledge-bases/{kb}",
        f"{base}/knowledge-bases/{kb}/documents/{docs[0]['id']}",
        f"{base}/tools",
        f"{base}/tools/{tool}",
        f"{base}/agents",
        f"{base}/runs",
        f"{base}/runs/{a_run.id}",
        f"{base}/runs/{a_run.id}/events",
    ]
    writes = [
        (f"{base}/knowledge-bases/{kb}/search", {"query": "fesih"}),
        (f"{base}/tools/{tool}/actions/run_sql/invoke", {"arguments": {"sql": "SELECT 1"}}),
        (f"{base}/agents/sozlesme-asistani/runs", {"input": "Merhaba"}),
    ]
    wrong = []  # every path is checked; the report lists all that differ
    for path in reads:
        assert owner.get(path).status_code == 200, path  # control: A sees it
        r = outsider.get(path)
        if r.status_code != iso["expected_status"]:
            wrong.append((path.replace(base, "A"), r.status_code, r.json()["error"]["code"]))
        assert a_pid not in r.text and docs[0]["filename"] not in r.text, path
    for path, body in writes:
        r = outsider.post(path, json=body)
        if r.status_code != iso["expected_status"]:
            wrong.append((path.replace(base, "A"), r.status_code, r.json()["error"]["code"]))
    print("F10 differing endpoints:", json.dumps(wrong))  # full list for the report (-s)
    assert not wrong, wrong


def test_18_f10_5_listing_does_not_leak(pair):
    iso, owner, a_pid, outsider = pair
    b_pid = outsider.project_id(iso["viewer_project"])
    a_agents = {a["id"] for a in owner.get(f"/api/v1/projects/{a_pid}/agents").json()["items"]}
    b_agents = {a["id"] for a in outsider.get(f"/api/v1/projects/{b_pid}/agents").json()["items"]}
    assert a_agents and not (a_agents & b_agents)
    a_kbs = {k["id"] for k in owner.get(f"/api/v1/projects/{a_pid}/knowledge-bases").json()["data"]}
    b_kbs = {
        k["id"] for k in outsider.get(f"/api/v1/projects/{b_pid}/knowledge-bases").json()["data"]
    }
    assert a_kbs and not (a_kbs & b_kbs)


def test_18_f10_6_trace_chain(pair, a_run):
    """run → sources (document ids) → llm_call.litellm_call_id → the Langfuse trace of the run,
    read back through Langfuse's public API."""
    _, owner, a_pid, _ = pair
    events = owner.run_events(a_pid, a_run.id)
    sources = [s for e in events if e["type"] == "sources" for s in e["payload"]["selected"]]
    assert sources and all(s["document_id"] for s in sources), sources
    calls = [e["payload"] for e in events if e["type"] == "llm_call"]
    assert calls and all(c.get("litellm_call_id") for c in calls), calls
    trace_id = a_run.detail.get("langfuse_trace_id")
    assert trace_id, a_run.detail
    host = os.environ.get("LANGFUSE_HOST", "http://langfuse-web:3000")
    auth = (os.environ["LANGFUSE_PUBLIC_KEY"], os.environ["LANGFUSE_SECRET_KEY"])
    deadline = time.monotonic() + TRACE_WAIT_S  # ingestion is asynchronous
    while True:
        r = httpx.get(f"{host}/api/public/traces/{trace_id}", auth=auth, timeout=10)
        if r.status_code == 200 or time.monotonic() > deadline:
            break
        time.sleep(3)
    assert r.status_code == 200, (r.status_code, r.text[:200])
    assert r.json()["id"] == trace_id


def test_18_f10_7_deleted_source_keeps_reference_without_content(pair):
    """A document deleted after a run: the run's sources event still names it (audit), carries
    no passage text, and the document itself is gone."""
    _, owner, a_pid, _ = pair
    tag = uuid.uuid4().hex[:8]
    base = f"/api/v1/projects/{a_pid}"
    kb = owner.post(f"{base}/knowledge-bases", json={"key": f"e2e-silme-{tag}", "name": tag})
    assert kb.status_code == 201, kb.text
    kb_id = kb.json()["id"]
    word = f"silmesinamasi{tag}"
    up = owner.post(
        f"{base}/knowledge-bases/{kb_id}/documents",
        files={"files": (f"silme-{tag}.txt", _procedure(word).encode())},
        data={"acl_open": "true"},
    )
    assert up.status_code == 202, up.text
    doc_id = up.json()["data"][0]["document"]["id"]
    doc_url = f"{base}/knowledge-bases/{kb_id}/documents/{doc_id}"
    deadline = time.monotonic() + 300
    while (status := owner.get(doc_url).json()["status"]) not in INDEX_TERMINAL:
        assert time.monotonic() < deadline, status
        time.sleep(2)
    assert status == "indexed", status
    agent_key = f"e2e-silme-{tag}"
    agent = owner.post(
        f"{base}/agents", json={"key": agent_key, "name": agent_key, "model": "chat-default"}
    )
    assert agent.status_code == 201, agent.text
    template = load("agents/sozlesme-asistani.json")["definition"]
    knowledge = [{**template["knowledge"][0], "kb_key": f"e2e-silme-{tag}"}]
    definition = {**template, "knowledge": knowledge}
    put = owner.http.put(
        f"{base}/agents/{agent.json()['id']}/versions/1", json={"definition": definition}
    )
    assert put.status_code == 200, put.text
    pub = owner.post(f"{base}/agents/{agent.json()['id']}/publish", json={"version": 1})
    assert pub.status_code == 200, pub.text
    run = owner.settle(a_pid, owner.start_run(a_pid, agent_key, f"{word} ne kadar tutulur?"))
    deleted = owner.http.delete(doc_url)
    assert deleted.status_code == 204, deleted.text
    events = owner.run_events(a_pid, run.id)
    refs = [s for e in events if e["type"] == "sources" for s in e["payload"]["selected"]]
    assert any(s["document_id"] == doc_id for s in refs), refs
    assert word not in str(refs)  # reference only, no passage text
    assert owner.get(doc_url).status_code == 404
