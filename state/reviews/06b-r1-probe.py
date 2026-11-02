"""Reviewer probes for 06b (facade). Copied into backend/tests/integration/ of the review
worktree, removed afterwards. Real LiteLLM + fake provider, as the worker's tests."""
import json
import uuid

import pytest

from tests.integration.facade_support import *  # noqa: F403 - fixtures
from tests.integration.facade_support import denied_rows, make_key, project_key
from tests.integration.litellm_support import fake_requests
from tests.integration.test_06b_direct import (  # noqa: F401 - fixtures + helpers
    EMAIL,
    SECRET,
    TOOL,
    _policy,
    _tool_turn,
    direct,
    facade_settings,
)

pytestmark = pytest.mark.usefixtures("clean_litellm")


def _raw(client, body):
    return client._client.post("/v1/chat/completions", json=body, headers=client.headers())


def test_p1_fields_other_than_content_reach_the_provider(direct):
    project, console, key, client = direct
    body = {
        "model": "chat-default",
        "messages": [{"role": "user", "content": "hello", "name": EMAIL}],
        "stop": [EMAIL],
        "response_format": {"type": "json_schema", "json_schema": {"name": "x", "description": f"mail {EMAIL}",
                                                                  "schema": {"type": "object"}}},
    }
    response = _raw(client, body)
    print("P1 status:", response.status_code, response.text[:200])
    sent = json.dumps(fake_requests()[-1], ensure_ascii=False) if fake_requests() else ""
    print("P1 provider saw e-mail:", EMAIL in sent, "| name field present:", '"name"' in sent)
    for label, snippet in (("name", f'"name": "{EMAIL}"'), ("stop", EMAIL)):
        print("P1", label, "reaches provider unmasked:", snippet in sent)


def test_p2_placeholders_reach_the_client(direct):
    project, console, key, client = direct
    response = _raw(client, {"model": "tooly", "messages": _tool_turn(f"kayit {EMAIL}"), "tools": [TOOL]})
    assert response.status_code == 200, response.text
    text = response.json()["choices"][0]["message"]["content"]
    print("P2 client text:", text)
    print("P2 raw e-mail back to client:", EMAIL in text, "| placeholder shown:", "<<PII_" in text)


def test_p3_stream_leaks_when_only_the_rule_is_enforce(direct):
    project, console, key, client = direct
    # policy mode monitor, the rule's own mode enforce (Rule.mode, 08 fix)
    _policy(console, project, [{"type": "secrets", "action": "block", "stages": ["output.pre"], "mode": "enforce"}],
            mode="monitor")
    non_stream = _raw(client, {"model": "tooly", "messages": _tool_turn(SECRET), "tools": [TOOL]})
    print("P3 non-stream:", non_stream.status_code, "secret in body:", SECRET in non_stream.text)
    status, chunks, lines = client.stream("tooly", messages=_tool_turn(SECRET), tools=[TOOL])
    joined = "\n".join(lines)
    print("P3 stream status:", status, "| secret reached client in stream:", SECRET in joined)
    print("P3 first progress chunk:", chunks[0].get("x_platform") if chunks else None)


def test_p4b_impersonation_matrix(direct, make_user, pg, facade):
    project, console, key, _ = direct
    imp = make_key(console, project, scopes=["chat_direct", "impersonate"])
    c = facade(imp)
    _, outsider = make_user()  # exists, member of nothing
    unknown = f"nobody-{uuid.uuid4().hex[:6]}@example.test"
    r_unknown = c.chat("chat-default", user=unknown)
    imp2 = make_key(console, project, scopes=["chat_direct", "impersonate"])  # the audit throttle is per key
    r_outsider = facade(imp2).chat("chat-default", user=outsider)
    print("P4 unknown :", r_unknown.status_code, r_unknown.content)
    print("P4 outsider:", r_outsider.status_code, r_outsider.content)
    assert r_unknown.status_code == r_outsider.status_code == 403
    assert r_unknown.content == r_outsider.content
    keep = {"content-type", "content-length"}
    h1 = {k: v for k, v in r_unknown.headers.items() if k.lower() in keep}
    h2 = {k: v for k, v in r_outsider.headers.items() if k.lower() in keep}
    assert h1 == h2
    reasons = [r.get("reason") for r in denied_rows(pg, imp["id"]) + denied_rows(pg, imp2["id"])]
    print("P4 audit reasons:", reasons)
    assert sorted(reasons) == ["not_member", "user_not_mapped"]
    # a member passes
    _, member = make_user(memberships={project: ("user", "edit")})
    ok = c.chat("chat-default", user=member)
    print("P4 member:", ok.status_code)
    # no-scope key + user: label only, audited
    plain = facade(key)
    plain_resp = plain.chat("chat-default", user=outsider)
    print("P4 no-scope key + outsider email:", plain_resp.status_code)
    assert plain_resp.status_code == 200
    assert "scope_missing" in [r.get("reason") for r in denied_rows(pg, key["id"])]
    # e-mail value is never written to the audit row
    rows = pg.execute("SELECT after::text FROM audit_events WHERE action='impersonation_denied'").fetchall()
    assert all(unknown not in r[0] and outsider not in r[0] for r in rows)


def test_p5_resume_of_foreign_or_missing_run_is_404(direct, facade, pg):
    project, console, key, _ = direct
    agents = facade(make_key(console, project, scopes=["agents"]))
    for rid in (str(uuid.uuid4()), "not-a-uuid"):
        r = agents.chat(f"agent:{project_key(pg, project)}/asistan", headers={"X-Resume-Run-Id": rid})
        print("P5", rid[:8], r.status_code, r.json().get("error", {}).get("code"))
        assert r.status_code == 404
