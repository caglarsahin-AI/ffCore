"""13b negative e2e tests (K-13b-0001): the refusals of the PoC paths that no plan/18 scenario
test covers yet, each with its status and error code (codes read from the source, not guessed).
They run on the scenario stack with fake-llm; every refusal must be visible and coded, never a
silent success (plan/18 "Kurallar")."""

import uuid

import httpx
import pytest

from tests.e2e.scenarios.conftest import BACKEND_URL, load

from .conftest import PROJECT

API = "/api/v1"
SECRET = "sk-ant-" + "REDACTED" * 4 + "00"  # vendor key shape, not a real key


def code(r: httpx.Response) -> tuple[int, str]:
    return r.status_code, r.json()["error"]["code"]


# --- auth -------------------------------------------------------------------------------


def test_13b_neg_auth_1_no_session_is_401(login):
    pid = login(PROJECT, "analyst", "edit").project_id(PROJECT)
    with httpx.Client(base_url=BACKEND_URL, timeout=30) as anonymous:
        for path in ("/auth/me", f"/projects/{pid}/agents", f"/projects/{pid}/runs"):
            assert code(anonymous.get(API + path)) == (401, "unauthenticated"), path


def test_13b_neg_auth_2_cookie_change_from_a_foreign_origin_is_403(login, answered_run):
    """C6: a cookie-authenticated change from another origin is refused."""
    analyst = login(PROJECT, "analyst", "edit")
    pid, run = answered_run
    r = analyst.post(
        f"{API}/projects/{pid}/runs/{run.id}/feedback",
        json={"vote": "correct"},
        headers={"Origin": "https://elsewhere.example.test"},
    )
    assert code(r) == (403, "cross_origin_forbidden")


# --- read-only access ---------------------------------------------------------------------


def test_13b_neg_access_1_read_member_cannot_change_anything(login, answered_run):
    owner = login(PROJECT, "admin", "edit")
    reader = login(PROJECT, "admin", "read")
    pid, run = answered_run
    base = f"{API}/projects/{pid}"
    kb = owner.kb_id(pid, "sozlesmeler")
    tool = owner.tool_id(pid, "mcp-sql")
    agent = next(
        a for a in owner.get(f"{base}/agents").json()["items"] if a["key"] == "sozlesme-asistani"
    )
    attempts = {
        "create knowledge base": ("POST", f"{base}/knowledge-bases", {"json": {"key": "neg-kb", "name": "x"}}),
        "upload document": (
            "POST",
            f"{base}/knowledge-bases/{kb}/documents",
            {"files": {"files": ("neg.txt", b"Madde 1 - deneme.")}, "data": {"acl_open": "true"}},
        ),
        "publish agent": ("POST", f"{base}/agents/{agent['id']}/publish", {"json": {"version": 1}}),
        "invoke tool": (
            "POST",
            f"{base}/tools/{tool}/actions/run_sql/invoke",
            {"json": {"arguments": {"sql": "SELECT 1", "reason": "neg"}}},
        ),
        "give feedback": ("POST", f"{base}/runs/{run.id}/feedback", {"json": {"vote": "wrong"}}),
    }
    wrong = {}
    for name, (method, path, kw) in attempts.items():
        r = reader.http.request(method, path, **kw)
        if code(r) != (403, "read_only_access"):
            wrong[name] = (r.status_code, r.text[:160])
    assert not wrong, wrong


# --- runs -----------------------------------------------------------------------------------


def test_13b_neg_run_1_unpublished_agent_is_404(login):
    analyst = login(PROJECT, "analyst", "edit")
    pid = analyst.project_id(PROJECT)
    key = f"neg-draft-{uuid.uuid4().hex[:8]}"
    created = analyst.post(
        f"{API}/projects/{pid}/agents", json={"key": key, "name": key, "model": "chat-default"}
    )
    assert created.status_code == 201, created.text
    r = analyst.post(f"{API}/projects/{pid}/agents/{key}/runs", json={"input": "Merhaba"})
    assert code(r) == (404, "agent_not_published")


def test_13b_neg_run_2_unknown_variable_is_422(login):
    analyst = login(PROJECT, "analyst", "edit")
    pid = analyst.project_id(PROJECT)
    r = analyst.post(
        f"{API}/projects/{pid}/agents/sozlesme-asistani/runs",
        json={"input": "Merhaba", "variables": {"olmayan_degisken": "x"}},
    )
    assert code(r) == (422, "variable_unknown")


def test_13b_neg_run_3_input_over_the_limit_is_422_not_cut(login, fake_llm):
    analyst = login(PROJECT, "analyst", "edit")
    pid = analyst.project_id(PROJECT)
    fake_llm.reset()
    r = analyst.post(
        f"{API}/projects/{pid}/agents/sozlesme-asistani/runs", json={"input": "a" * 20_001}
    )
    assert code(r) == (422, "validation_error")
    assert fake_llm.requests() == []


def test_13b_neg_run_4_resuming_a_finished_run_is_409(login, answered_run):
    analyst = login(PROJECT, "analyst", "edit")
    pid, run = answered_run
    r = analyst.post(f"{API}/projects/{pid}/runs/{run.id}/resume", json={"decision": "approved"})
    assert code(r) == (409, "run_not_waiting")


# --- tools ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "endpoint",
    ["http://169.254.169.254/mcp", "http://10.20.30.40:8000/mcp", "http://127.0.0.1:9/mcp"],
)
def test_13b_neg_tool_1_private_endpoints_refused_at_registration(login, endpoint):
    admin = login(PROJECT, "admin", "edit")
    pid = admin.project_id(PROJECT)
    body = {
        "key": f"neg-{uuid.uuid4().hex[:8]}",
        "name": "neg",
        "kind": "mcp",
        "endpoint_url": endpoint,
        "auth": {"type": "none"},
    }
    r = admin.post(f"{API}/projects/{pid}/tools", json=body)
    status, err = code(r)
    assert status == 400 and err.startswith("egress_"), (endpoint, status, err)


# --- guardrails -----------------------------------------------------------------------------


def test_13b_neg_guard_1_enforced_secrets_rule_stops_the_run_before_the_model(login, fake_llm):
    """A project policy that enforces the secrets rule: a message with a key-shaped value fails
    with guardrail_block and nothing reaches the provider."""
    admin = login(PROJECT, "admin", "edit")
    analyst = login(PROJECT, "analyst", "edit")
    pid = admin.project_id(PROJECT)
    tag = uuid.uuid4().hex[:8]
    policy = admin.post(
        f"{API}/projects/{pid}/guardrail-policies",
        json={
            "key": f"neg-secrets-{tag}",
            "name": "neg secrets",
            "mode": "enforce",
            "rules": [{"type": "secrets", "action": "block", "stages": ["input.pre", "egress"]}],
        },
    )
    assert policy.status_code == 201, policy.text
    template = load("agents/sozlesme-asistani.json")["definition"]
    definition = {**template, "knowledge": [], "guardrail_policy_key": f"neg-secrets-{tag}"}
    key = f"neg-guard-{tag}"
    agent = analyst.post(
        f"{API}/projects/{pid}/agents", json={"key": key, "name": key, "model": "chat-default"}
    )
    assert agent.status_code == 201, agent.text
    put = analyst.http.put(
        f"{API}/projects/{pid}/agents/{agent.json()['id']}/versions/1",
        json={"definition": definition},
    )
    assert put.status_code == 200, put.text
    published = analyst.post(f"{API}/projects/{pid}/agents/{agent.json()['id']}/publish", json={"version": 1})
    assert published.status_code == 200, published.text
    fake_llm.reset()
    run = analyst.settle(pid, analyst.start_run(pid, key, f"Bu anahtarı kontrol et: {SECRET}"))
    assert (run.detail["status"], run.detail["error_code"]) == ("failed", "guardrail_block")
    assert fake_llm.requests() == []


# --- approvals ------------------------------------------------------------------------------


def test_13b_neg_approval_1_expired_approval_closes_the_run():
    pytest.skip(
        "NOT_RUN: FOLLOWUP-111 (no way to trigger 07's TTL sweep from a test; APPROVAL_TTL_MIN "
        "is 60 min on the stack)"
    )


# --- audit ----------------------------------------------------------------------------------


def test_13b_neg_audit_1_seed_and_actions_are_in_the_project_audit(login, answered_run):
    """Brief 13 item 6: the steps show in the audit. The seed's changes and a feedback appear
    in the project's audit log; the read-only admin reads it, an analyst cannot."""
    analyst = login(PROJECT, "analyst", "edit")
    reader = login(PROJECT, "admin", "read")
    pid, run = answered_run
    given = analyst.post(
        f"{API}/projects/{pid}/runs/{run.id}/feedback", json={"vote": "partial", "note": "audit"}
    )
    assert given.status_code in (200, 409), given.text  # 409: already given by another test
    r = reader.get(f"{API}/audit", params={"project_id": pid, "limit": 1000})
    assert r.status_code == 200, r.text
    actions = {e["action"] for e in r.json()["data"]}
    expected = {
        "create_knowledge_base",
        "upload_documents",
        "create_tool",
        "discover_tool",
        "update_tool_action",
        "create_agent",
        "publish_agent",
        "give_feedback",
    }
    assert expected <= actions, expected - actions
    assert code(analyst.get(f"{API}/audit", params={"project_id": pid}))[0] == 403
