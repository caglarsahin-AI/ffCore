"""Reviewer probes for 06b r2 (facade), real LiteLLM + fake provider. Copied into
backend/tests/integration/ of the review worktree, removed afterwards."""
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


def _provider_text():
    return json.dumps(fake_requests(), ensure_ascii=False)


BASE = {"model": "chat-default", "messages": [{"role": "user", "content": "hello"}]}


@pytest.mark.parametrize(
    "label,patch",
    [
        ("message.name", {"messages": [{"role": "user", "content": "hello", "name": EMAIL}]}),
        ("stop", {"stop": [EMAIL]}),
        ("stop_str", {"stop": EMAIL}),
        ("response_format", {"response_format": {"type": "json_schema", "json_schema": {
            "name": "x", "description": f"mail {EMAIL}", "schema": {"type": "object"}}}}),
        ("tool_choice", {"tools": [TOOL], "tool_choice": {"type": "function", "function": {"name": EMAIL}}}),
        ("tools.description", {"tools": [{"type": "function", "function": {
            "name": "lookup", "description": f"mail {EMAIL}", "parameters": {"type": "object", "properties": {}}}}]}),
        ("tool_call_id", {"messages": [
            {"role": "user", "content": "x"},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "lookup", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": EMAIL, "content": "r"}], "tools": [TOOL]}),
        # numeric parameters carrying text (not in TEXT_PARAMS): the residual question
        ("top_p", {"top_p": EMAIL}),
        ("seed", {"seed": EMAIL}),
        ("presence_penalty", {"presence_penalty": EMAIL}),
        ("frequency_penalty", {"frequency_penalty": EMAIL}),
        ("logit_bias", {"logit_bias": {"12": EMAIL}}),
    ],
)
def test_p1_every_field_no_raw_email_at_the_provider(direct, label, patch):
    project, console, key, client = direct
    response = _raw(client, BASE | patch)
    seen = _provider_text()
    leaked = EMAIL in seen
    print(f"P1 {label}: status={response.status_code} code={response.json().get('error', {}).get('code') if response.status_code >= 400 else '-'} provider_saw_email={leaked}")
    assert not leaked, f"{label} reached the provider unmasked"


def test_p2_unknown_message_field_400_and_roundtrip_fields(direct):
    project, console, key, client = direct
    r = _raw(client, BASE | {"messages": [{"role": "user", "content": "hello", "x_secret": EMAIL}]})
    print("P2 unknown field:", r.status_code, r.json()["error"]["code"], r.json()["error"]["message"][:90])
    assert r.status_code == 400 and r.json()["error"]["code"] == "unsupported_field"
    assert EMAIL not in _provider_text() and fake_requests() == []
    # fields an OpenAI SDK echoes when the assistant message of an earlier answer is sent back
    for field, value in (("annotations", []), ("refusal", None), ("audio", None), ("function_call", None),
                         ("annotations", [{"type": "url_citation"}])):
        rr = _raw(client, BASE | {"messages": [
            {"role": "user", "content": "q"},
            {"role": "assistant", "content": "a", field: value},
            {"role": "user", "content": "next"}]})
        print(f"P2 echoed assistant field {field}={value!r}: {rr.status_code}")


def test_p3_user_label_not_forwarded(direct):
    project, console, key, client = direct
    r = _raw(client, BASE | {"user": EMAIL})
    assert r.status_code == 200, r.text
    seen = _provider_text()
    print("P3 user label at provider:", EMAIL in seen)
    assert EMAIL not in seen


def test_p4_rule_enforce_buffers_and_blocks_stream_and_nonstream(direct):
    project, console, key, client = direct
    _policy(console, project, [{"type": "secrets", "action": "block", "stages": ["output.pre"], "mode": "enforce"}],
            mode="monitor")
    ns = _raw(client, {"model": "tooly", "messages": _tool_turn(SECRET), "tools": [TOOL]})
    status, chunks, lines = client.stream("tooly", messages=_tool_turn(SECRET), tools=[TOOL])
    joined = "\n".join(lines)
    print("P4 non-stream:", ns.status_code, "| stream:", status, "secret in stream:", SECRET in joined,
          "| first x_platform:", chunks[0].get("x_platform") if chunks else None)
    assert ns.status_code == 400 and SECRET not in ns.text
    assert SECRET not in joined
    assert chunks and chunks[0].get("x_platform") == {"event": "progress", "kind": "output_buffered"}


def test_p5_monitor_everywhere_streams_live_and_default_policy_unchanged(direct):
    project, console, key, client = direct
    # default built-in policy: egress rule is enforce but not on an output stage -> live stream
    status, chunks, lines = client.stream("chat-default")
    print("P5 default policy first chunk x_platform:", chunks[0].get("x_platform") if chunks else None)
    assert not any((c.get("x_platform") or {}).get("kind") == "output_buffered" for c in chunks)
    _policy(console, project, [{"type": "secrets", "action": "block", "stages": ["output.pre"]}], mode="monitor")
    status, chunks, lines = client.stream("tooly", messages=_tool_turn(SECRET), tools=[TOOL])
    print("P5 monitor policy + monitor rule: stream live ->", not any((c.get("x_platform") or {}).get("kind") == "output_buffered" for c in chunks))
    assert not any((c.get("x_platform") or {}).get("kind") == "output_buffered" for c in chunks)


def test_p6_enforced_at_semantics():
    from ffcore.guardrails.builtin import BUILTIN_DEFAULT
    from ffcore.guardrails.engine import enforced_at
    from ffcore.guardrails.schemas import Rule

    out = ("output.pre", "output.stream.delta")
    assert enforced_at(BUILTIN_DEFAULT, out) is False
    spec = BUILTIN_DEFAULT.spec
    def policy(mode, rules):
        return BUILTIN_DEFAULT.__class__(key="x", spec=spec.model_copy(update={"mode": mode, "rules": rules}),
                                         pii_policies=BUILTIN_DEFAULT.pii_policies, builtin=False)
    r_out_enf = Rule(type="secrets", action="block", stages=["output.pre"], mode="enforce")
    r_out = Rule(type="secrets", action="block", stages=["output.pre"])
    r_in_enf = Rule(type="secrets", action="block", stages=["input.pre"], mode="enforce")
    assert enforced_at(policy("monitor", [r_out_enf]), out) is True
    assert enforced_at(policy("enforce", [r_out]), out) is True
    assert enforced_at(policy("monitor", [r_out]), out) is False
    assert enforced_at(policy("monitor", [r_in_enf]), out) is False
    assert enforced_at(policy("enforce", [r_in_enf]), out) is False     # enforce policy, rule on another stage
    assert enforced_at(policy("off", [r_out_enf]), out) is False
    assert enforced_at(policy("enforce", [Rule(type="secrets", action="block", stages=["output.pre"], mode="monitor")]), out) is False
    print("P6 enforced_at semantics OK")


def test_p7_impersonation_still_byte_equal(direct, make_user, pg, facade):
    project, console, key, _ = direct
    imp, imp2 = (make_key(console, project, scopes=["chat_direct", "impersonate"]) for _ in range(2))
    _, outsider = make_user()
    a = facade(imp).chat("chat-default", user=f"nobody-{uuid.uuid4().hex[:6]}@example.test")
    b = facade(imp2).chat("chat-default", user=outsider)
    assert a.status_code == b.status_code == 403 and a.content == b.content
    print("P7 byte-equal 403 OK")


# ---- r3 additions ----
@pytest.mark.parametrize("name", ["temperature", "top_p", "presence_penalty", "frequency_penalty", "seed",
                                  "max_tokens", "max_completion_tokens", "n"])
@pytest.mark.parametrize("bad", [EMAIL, True, [1], {"a": 1}])
def test_r3_numeric_wrong_type_400_invalid_parameter(direct, name, bad):
    project, console, key, client = direct
    r = _raw(client, BASE | {name: bad})
    body = r.json()
    ok = r.status_code == 400 and body["error"]["code"] == "invalid_parameter" and body["error"].get("param") == name
    print(f"R3 {name}={str(bad)[:12]!r}: {r.status_code} {body['error']['code']} param={body['error'].get('param')} echoed={EMAIL in r.text}")
    assert ok
    assert EMAIL not in r.text and fake_requests() == []


@pytest.mark.parametrize("name,value", [("temperature", 2.5), ("temperature", -0.1), ("top_p", 1.5), ("presence_penalty", 3),
                                        ("frequency_penalty", -2.5), ("max_tokens", 0), ("n", 2), ("seed", 1.5), ("max_tokens", 1.5)])
def test_r3_numeric_out_of_range_or_wrong_integer(direct, name, value):
    project, console, key, client = direct
    r = _raw(client, BASE | {name: value})
    print(f"R3 range {name}={value}: {r.status_code} {r.json()['error']['code']} {r.json()['error'].get('param')}")
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_parameter" and fake_requests() == []


@pytest.mark.parametrize("name,value", [("temperature", 0), ("temperature", 2), ("top_p", 1), ("presence_penalty", -2),
                                        ("frequency_penalty", 0.5), ("seed", 7), ("max_tokens", 5), ("n", 1)])
def test_r3_valid_numbers_still_pass(direct, name, value):
    project, console, key, client = direct
    r = _raw(client, BASE | {name: value})
    assert r.status_code == 200, (name, value, r.text[:200])


@pytest.mark.parametrize("raw", ['"top_p": NaN', '"temperature": Infinity', '"seed": -Infinity', '"presence_penalty": NaN'])
def test_r3_nan_infinity_json_constants(direct, raw):
    project, console, key, client = direct
    body = '{"model":"chat-default","messages":[{"role":"user","content":"hello"}],' + raw + "}"
    r = client._client.post("/v1/chat/completions", content=body, headers={**client.headers(), "content-type": "application/json"})
    print(f"R3 {raw}: status={r.status_code} code={r.json().get('error', {}).get('code') if r.headers.get('content-type','').startswith('application/json') else r.text[:80]} provider_calls={len(fake_requests())}")


def test_r3_stream_bad_param_is_plain_http_400(direct):
    project, console, key, client = direct
    status, body, lines = client.stream("chat-default", top_p=EMAIL)
    print("R3 stream bad param:", status, body["error"]["code"] if isinstance(body, dict) else body)
    assert status == 400 and body["error"]["code"] == "invalid_parameter" and EMAIL not in json.dumps(body)


def test_r3_unknown_param_unsupported_field(direct):
    project, console, key, client = direct
    r = _raw(client, BASE | {"metadata": {"k": EMAIL}, "store": True})
    print("R3 unknown params:", r.status_code, r.json()["error"]["code"])
    assert r.status_code == 400 and r.json()["error"]["code"] == "unsupported_field" and fake_requests() == []


def test_r3_echo_fields_accepted_and_never_forwarded(direct):
    project, console, key, client = direct
    msgs = [{"role": "user", "content": "q"},
            {"role": "assistant", "content": "a", "annotations": [{"type": "url_citation", "url_citation": {"url": f"ffcore://x/{EMAIL}"}}],
             "refusal": f"no {EMAIL}", "audio": {"id": "x"}},
            {"role": "user", "content": "next"}]
    r = _raw(client, BASE | {"messages": msgs})
    sent = json.dumps(fake_requests()[-1].get("messages"), ensure_ascii=False)
    print("R3 echo:", r.status_code, "| echo values at provider:", EMAIL in sent, "annotations key at provider:", "annotations" in sent)
    assert r.status_code == 200 and EMAIL not in sent and "annotations" not in sent and "refusal" not in sent
    # echo fields on a non-assistant message stay refused
    r2 = _raw(client, BASE | {"messages": [{"role": "user", "content": "q", "annotations": []}]})
    print("R3 echo on user message:", r2.status_code, r2.json()["error"]["code"])
    assert r2.status_code == 400 and r2.json()["error"]["code"] == "unsupported_field"


def test_r3_agent_path_params_checked_before_a_run(owner, facade, pg):
    from tests.integration.runs_fixtures import publish
    from tests.integration.runtime_support import definition

    project, console = owner
    publish(pg, project, definition())
    agents = facade(make_key(console, project, scopes=["agents"]))
    before = pg.execute("SELECT count(*) FROM runs WHERE project_id=%s", (project,)).fetchone()[0]
    model = f"agent:{project_key(pg, project)}/asistan"
    for patch in ({"top_p": EMAIL}, {"temperature": 9}, {"n": 3}, {"metadata": {"a": 1}}):
        r = agents._client.post("/v1/chat/completions", json={"model": model, "messages": [{"role": "user", "content": "hi"}]} | patch,
                                headers=agents.headers())
        print("R3 agent", patch, r.status_code, r.json()["error"]["code"], r.json()["error"].get("param"))
        assert r.status_code == 400 and EMAIL not in r.text
    after = pg.execute("SELECT count(*) FROM runs WHERE project_id=%s", (project,)).fetchone()[0]
    assert after == before, "a rejected request must not start a run"
