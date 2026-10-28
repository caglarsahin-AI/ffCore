"""08-lite engine: evaluate(text, stage, policy) -> Decision (C4), rule chain, modes, on_error."""

import asyncio

import pytest

from ffcore.guardrails import engine
from ffcore.guardrails.builtin import BUILTIN_DEFAULT
from ffcore.guardrails.categories import ACTIONS, STAGES
from ffcore.guardrails.engine import (
    Decision,
    EgressStageDisabled,
    EvalContext,
    TextTooLong,
    evaluate,
)
from ffcore.guardrails.masking import MemoryTokenStore
from ffcore.guardrails.schemas import (
    GuardrailConfigError,
    PiiPolicySpec,
    PolicySpec,
    ResolvedPolicy,
    Rule,
    validate_pii_policy,
    validate_policy,
)

PII = PiiPolicySpec(
    engine="regex",
    default_action="redact",
    categories={
        "TR_NATIONAL_ID": {"enabled": True, "severity": "high"},
        "EMAIL_ADDRESS": {"enabled": True, "severity": "medium", "action": "mask"},
        "TR_PHONE": {"enabled": True, "severity": "medium"},
    },
)
TEXT = "TC 10000000146, mail ayse@ornek.com"
SECRET_TEXT = "key sk-ant-REDACTEDREDACTEDREDACTEDREDACTED00 burada"


def policy(*rules, mode="enforce", short_circuit=True, on_error="block", message=None):
    spec = PolicySpec(
        rules=list(rules),
        mode=mode,
        short_circuit=short_circuit,
        on_error=on_error,
        block_message=message or {"en": "Blocked by policy.", "tr": "Politika engelledi."},
    )
    return ResolvedPolicy(key="p", spec=spec, pii_policies={"pii": PII}, builtin=False)


def pii_rule(action=None, stages=("input.pre",)):
    return Rule(type="pii", action=action, stages=list(stages), pii_policy_key="pii")


def secrets_rule(action="block", stages=("input.pre",)):
    return Rule(type="secrets", action=action, stages=list(stages))


def run(text, stage="input.pre", pol=None, **ctx):
    ctx.setdefault("egress_enabled", True)
    return asyncio.run(evaluate(text, stage, pol or policy(pii_rule()), ctx=EvalContext(**ctx)))


def test_c4_stage_and_action_lists():
    assert STAGES == (
        "prompt.pre",
        "input.pre",
        "output.pre",
        "output.stream.delta",
        "tool.pre",
        "tool.post",
        "egress",
    )
    assert ACTIONS == ("block", "redact", "mask", "tokenize", "warn", "log")
    assert {f.name for f in engine.dataclass_fields(Decision)} >= {"action", "text_out", "events"}


def test_08_4_block_decision_event_message():
    decision = run(SECRET_TEXT, pol=policy(secrets_rule()), locale="tr")
    assert decision.action == "block"
    assert decision.text_out == ""
    assert decision.message == "Politika engelledi."
    assert decision.reference_id
    [event] = decision.events
    assert (event.status, event.action_taken, event.rule) == ("failed", "block", "secrets#0")
    assert run(SECRET_TEXT, pol=policy(secrets_rule()), locale="en").message == "Blocked by policy."


def test_08_4_missing_locale_message_falls_back_to_english():
    decision = run(SECRET_TEXT, pol=policy(secrets_rule(), message={"en": "Blocked."}), locale="tr")
    assert decision.message == "Blocked."


def test_08_4_block_cuts_the_chain():
    decision = run(SECRET_TEXT, pol=policy(secrets_rule(), pii_rule()))
    assert [e.rule for e in decision.events] == ["secrets#0"]


def test_08_9_short_circuit_off_runs_every_rule_but_still_blocks():
    decision = run(
        SECRET_TEXT + " " + TEXT, pol=policy(secrets_rule(), pii_rule(), short_circuit=False)
    )
    assert [e.rule for e in decision.events] == ["secrets#0", "pii#1"]
    assert decision.action == "block"


def test_08_9_text_out_flows_into_the_next_rule():
    # The first rule redacts the e-mail; the second (mask) no longer sees it.
    first = Rule(type="pii", action="redact", stages=["input.pre"], pii_policy_key="pii")
    second = Rule(type="pii", action="mask", stages=["input.pre"], pii_policy_key="pii")
    decision = run(TEXT, pol=policy(first, second))
    assert decision.text_out == "TC [TR_NATIONAL_ID], mail [EMAIL_ADDRESS]"
    assert decision.events[1].findings == []
    assert decision.action == "redact"


def test_08_9_per_category_actions_and_strongest_action():
    decision = run(TEXT)  # rule without action: TC -> default redact, e-mail -> mask
    assert decision.text_out == "TC [TR_NATIONAL_ID], mail a***@ornek.com"
    assert decision.action in ("redact", "mask")
    assert decision.events[0].status == "redacted"


def test_08_5_monitor_records_not_applies():
    decision = run(TEXT, pol=policy(pii_rule(), mode="monitor"))
    assert decision.action == "allow"
    assert decision.text_out == TEXT
    [event] = decision.events
    assert event.mode == "monitor"
    assert event.action_taken == "redact"
    assert event.status == "passed"
    assert {f["category"] for f in event.findings} == {"TR_NATIONAL_ID", "EMAIL_ADDRESS"}
    blocked = run(SECRET_TEXT, pol=policy(secrets_rule(), mode="monitor"))
    assert blocked.action == "allow" and blocked.text_out == SECRET_TEXT
    assert blocked.events[0].action_taken == "block"


def test_08_5_off_mode_evaluates_nothing():
    decision = run(SECRET_TEXT, pol=policy(secrets_rule(), mode="off"))
    assert (decision.action, decision.text_out, decision.events) == ("allow", SECRET_TEXT, [])


def test_08_10_on_error_fail_closed(monkeypatch):
    def broken(*_args, **_kwargs):
        raise RuntimeError("recognizer crashed")

    monkeypatch.setattr(engine, "recognize", broken)
    closed = run(TEXT)
    assert closed.action == "block"
    assert closed.events[0].status == "failed"
    assert closed.events[0].error == "RuntimeError"
    opened = run(TEXT, pol=policy(pii_rule(), on_error="allow"))
    assert opened.action == "allow"
    assert opened.text_out == TEXT
    assert (opened.events[0].status, opened.events[0].action_taken) == ("failed", "log")


def test_08_11_secrets_rule():
    cases = [
        "anahtar sk-ant-REDACTEDREDACTEDREDACTEDREDACTED00",
        "AWS AKIAABCDEFGHIJKLMNOP",
        "db postgresql://app:Sup3rS3cret@db:5432/x",
        "token tok_8c0aa059260cc557e9c5953580addee2 olarak tanımlandı",
        "Geçici şifre: Bahar6531!",
    ]
    for text in cases:
        assert run(text, pol=policy(secrets_rule())).action == "block", text
    for text in (
        "Sözleşmenin 10. maddesine göre fesih bildirim süresi 90 gündür.",
        "Kayıt 3f2b8c1e-9a4d-4e5f-8b6a-1c2d3e4f5a6b ile açıldı.",
        "Fatura tutarı 1.212.500 TL, vadesi 45 gün.",
    ):
        assert run(text, pol=policy(secrets_rule())).action == "allow", text


def test_08_12_tool_args_rule():
    rule = Rule(
        type="tool_args",
        action="block",
        stages=["tool.pre"],
        params={
            "tools": ["mcp-sql.run_sql"],
            "patterns": [r"\bpg_\w+", r"https?://"],
            "args": ["sql"],
        },
    )
    pol = policy(rule)
    bad = '{"sql": "SELECT * FROM pg_shadow", "reason": "x"}'
    assert run(bad, "tool.pre", pol, tool="mcp-sql.run_sql").action == "block"
    assert run(bad, "tool.pre", pol, tool="mcp-search.search_documents").action == "allow"
    ok = '{"sql": "SELECT 1", "reason": "pg_ only in reason"}'
    assert run(ok, "tool.pre", pol, tool="mcp-sql.run_sql").action == "allow"
    not_json = run("SELECT * FROM pg_shadow", "tool.pre", pol, tool="mcp-sql.run_sql")
    assert not_json.action == "block" and not_json.events[0].error == "ToolArgumentsNotObject"


def test_08_13_stage_binding():
    pol = policy(pii_rule(stages=("output.pre",)))
    assert run(TEXT, "input.pre", pol).events == []
    assert run(TEXT, "output.pre", pol).text_out != TEXT
    with pytest.raises(GuardrailConfigError) as err:
        run(TEXT, "input.post", pol)
    assert err.value.code == "stage_unknown"


def test_08_18_egress_flag():
    pol = policy(pii_rule(action="tokenize", stages=("egress",)))
    with pytest.raises(EgressStageDisabled):
        run(TEXT, "egress", pol, egress_enabled=False, run_id="r1", token_store=MemoryTokenStore())
    decision = run(TEXT, "egress", pol, run_id="r1", token_store=MemoryTokenStore())
    assert decision.text_out == "TC <<PII_1>>, mail <<PII_2>>"
    assert decision.action == "tokenize"


def test_08_9_text_limit_fails_loud():
    with pytest.raises(TextTooLong):
        run("a" * (engine.MAX_TEXT_CHARS + 1))


def test_08_20_events_masked():
    decision = run(TEXT, pol=policy(pii_rule(), mode="monitor"))
    event = decision.events[0]
    assert "10000000146" not in event.input_preview and "ayse@" not in event.input_preview
    assert len(event.input_preview) <= 60
    serialized = repr(event.matches) + repr(event.findings)
    assert "10000000146" not in serialized and "ayse@ornek.com" not in serialized
    assert all(f["evidence"] for f in event.findings)
    secret = run(SECRET_TEXT, pol=policy(secrets_rule()))
    assert "REDACTEDREDACTED" not in repr(secret.events)


def test_08_15_unsupported_rejected():
    def code(fn, *args):
        with pytest.raises(GuardrailConfigError) as err:
            fn(*args)
        return err.value.code

    assert (
        code(
            validate_policy,
            PolicySpec(rules=[Rule(type="injection", action="block", stages=["input.pre"])]),
            {},
        )
        == "rule_type_unsupported"
    )
    assert (
        code(validate_policy, PolicySpec(rules=[Rule(type="secrets", stages=["input.pre"])]), {})
        == "rule_action_required"
    )
    assert code(validate_policy, PolicySpec(rules=[pii_rule()]), {}) == "pii_policy_not_found"
    tool_rule = Rule(
        type="tool_args",
        action="block",
        stages=["input.pre"],
        params={"tools": ["*"], "patterns": ["x"]},
    )
    assert code(validate_policy, PolicySpec(rules=[tool_rule]), {}) == "rule_stage_invalid"
    bad_regex = Rule(
        type="tool_args",
        action="block",
        stages=["tool.pre"],
        params={"tools": ["*"], "patterns": ["("]},
    )
    assert code(validate_policy, PolicySpec(rules=[bad_regex]), {}) == "pattern_invalid"
    assert code(validate_pii_policy, PiiPolicySpec(engine="ner")) == "engine_unsupported"
    assert (
        code(validate_pii_policy, PiiPolicySpec(categories={"PERSON": {"enabled": True}}))
        == "category_unsupported"
    )
    assert (
        code(validate_pii_policy, PiiPolicySpec(categories={"TC_KIMLIK": {"enabled": True}}))
        == "category_unknown"
    )
    # A custom pattern makes a category without a built-in recognizer usable.
    validate_pii_policy(
        PiiPolicySpec(
            categories={"TR_TAX_ID": {"enabled": True}},
            custom_patterns=[{"name": "vkn", "category": "TR_TAX_ID", "pattern": r"\b\d{10}\b"}],
        )
    )
    validate_policy(PolicySpec(rules=[pii_rule()]), {"pii"})


def test_08_15_custom_pattern_and_min_confidence():
    pii = PiiPolicySpec(
        min_confidence=0.9,
        categories={"TR_TAX_ID": {"enabled": True}, "TR_PHONE": {"enabled": True}},
        custom_patterns=[
            {
                "name": "vkn",
                "category": "TR_TAX_ID",
                "pattern": r"(?<!\d)\d{10}(?!\d)",
                "score": 0.95,
            }
        ],
    )
    pol = ResolvedPolicy(
        key="p", spec=policy(pii_rule()).spec, pii_policies={"pii": pii}, builtin=False
    )
    # Phone without context scores 0.75 < 0.9 and is dropped; the custom VKN pattern matches.
    decision = asyncio.run(
        evaluate(
            "vergi 5450747061 ve 0532 256 60 38",
            "input.pre",
            pol,
            ctx=EvalContext(egress_enabled=True),
        )
    )
    assert decision.text_out == "vergi [TR_TAX_ID] ve 0532 256 60 38"
    assert decision.events[0].findings[0]["evidence"] == "custom pattern 'vkn'"


def test_08_s5_builtin_default_is_monitor_and_valid():
    assert BUILTIN_DEFAULT.key == "default"
    assert BUILTIN_DEFAULT.builtin
    assert BUILTIN_DEFAULT.spec.mode == "monitor"
    validate_policy(BUILTIN_DEFAULT.spec, set(BUILTIN_DEFAULT.pii_policies))
    for spec in BUILTIN_DEFAULT.pii_policies.values():
        validate_pii_policy(spec)
    egress_rules = [r for r in BUILTIN_DEFAULT.spec.rules if "egress" in r.stages]
    assert any(r.type == "pii" and r.action == "tokenize" for r in egress_rules)
    assert any(r.type == "secrets" and r.action == "block" for r in egress_rules)


def test_08_15_stream_stage_and_rewriting_tool_args_rejected():
    stream = Rule(type="secrets", action="block", stages=["output.stream.delta"])
    rewrite = Rule(
        type="tool_args",
        action="redact",
        stages=["tool.pre"],
        params={"tools": ["*"], "patterns": ["x"]},
    )
    for rule, code in ((stream, "rule_stage_unsupported"), (rewrite, "rule_action_invalid")):
        with pytest.raises(GuardrailConfigError) as err:
            validate_policy(PolicySpec(rules=[rule]), set())
        assert err.value.code == code
