"""fix/08-default-egress-enforce (K-SEN-0029 A, K-SEN-0030; plan/18 F4 findings):

1. The built-in `default` policy tokenizes PII at egress even though the policy is monitor: a
   rule may carry its own mode (additive `Rule.mode`), and the built-in egress PII rule is
   enforce. Everything else in the built-in policy stays monitor.
2. The secrets entropy check no longer takes identifiers made of plain words and numbers
   (document names such as `SZL-2025-003_temizlik-hizmet.txt`) for API tokens; random tokens
   are still caught.
"""

import asyncio

import pytest

from ffcore.guardrails.builtin import BUILTIN_DEFAULT
from ffcore.guardrails.engine import EvalContext, evaluate
from ffcore.guardrails.masking import MemoryTokenStore
from ffcore.guardrails.rules import find_secrets
from ffcore.guardrails.schemas import PolicySpec, ResolvedPolicy, Rule

TC = "25588971252"  # synthetic, valid checksum (13a pii-001)
QUESTION = f"Başvuru formunda TC kimlik numarası {TC} olarak yazılmış."
SOURCES = "SOURCES (newest first; cite as [n]):\n\n[1] SZL-2025-003_temizlik-hizmet.txt (updated"


def run(text, stage, policy=BUILTIN_DEFAULT):
    ctx = EvalContext(
        egress_enabled=True, run_id="r1", project_id="p1", token_store=MemoryTokenStore()
    )
    return asyncio.run(evaluate(text, stage, policy, ctx=ctx))


def test_08e_1_builtin_default_tokenizes_pii_at_egress():
    decision = run(f"{SOURCES}\n\nQUESTION:\n{QUESTION}", "egress")
    assert decision.action == "tokenize", decision.action
    assert TC not in decision.text_out
    pii = next(e for e in decision.events if e.rule.startswith("pii"))
    assert (pii.mode, pii.status) == ("enforce", "redacted")


def test_08e_2_builtin_default_other_rules_stay_monitor():
    decision = run(QUESTION, "input.pre")
    assert decision.action == "allow" and decision.text_out == QUESTION
    assert all(e.mode == "monitor" for e in decision.events)


def test_08e_3_builtin_secrets_do_not_block_at_egress():
    decision = run(f"anahtar tok_8c0aa059260cc557e9c5953580addee2 {QUESTION}", "egress")
    assert decision.action != "block"
    secrets = next(e for e in decision.events if e.rule.startswith("secrets"))
    assert secrets.mode == "monitor" and secrets.status == "passed"


def test_08e_4_rule_mode_overrides_policy_mode():
    rule = Rule(type="secrets", action="block", stages=["input.pre"], mode="enforce")
    policy = ResolvedPolicy(key="p", spec=PolicySpec(rules=[rule], mode="monitor"))
    assert run("anahtar tok_8c0aa059260cc557e9c5953580addee2", "input.pre", policy).action == (
        "block"
    )
    rule = Rule(type="secrets", action="block", stages=["input.pre"], mode="monitor")
    policy = ResolvedPolicy(key="p", spec=PolicySpec(rules=[rule], mode="enforce"))
    assert run("anahtar tok_8c0aa059260cc557e9c5953580addee2", "input.pre", policy).action == (
        "allow"
    )


@pytest.mark.parametrize(
    "identifier",
    [
        "SZL-2025-003_temizlik-hizmet",
        "SZL-2023-019_yazilim-lisans",
        "SZL-2025-012_yonetim-danismanlik",
        "hastane-a-admin-edit-example-test",
        "b-el-hijyeni-proseduru-klinik-b",
        "p4-sterilizasyon-calisma-esaslari",
        "PRSIM-1234-hastane-randevu-sistemi",  # ticket-style keys (K-SEN-0032)
    ],
)
def test_08e_5_word_and_number_identifiers_are_not_tokens(identifier):
    assert not find_secrets(f"[1] {identifier}.txt (updated 2025-09-01)"), identifier


@pytest.mark.parametrize(
    "token",
    [
        "tok_8c0aa059260cc557e9c5953580addee2",
        "8c0aa059260cc557e9c5953580addee2",  # 32 hex
        "Zx9qT2mK7vB4nR8wL1pY6sD3hJ5",
        "ab12Cd34-Ef56Gh78-Ij90Kl12-Mn34",
        "QmFzZTY0IGVuY29kZWQgc2VjcmV0IHZhbHVl",  # base64
        "API_KEY=Zx9qT2mK7vB4nR8wL1pY6sD3",  # KEY=value
        "sk-ant-REDACTEDREDACTEDREDACTEDREDACTED00",  # vendor pattern
        "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8",  # vendor pattern
        # review r1 MAJOR-1: separated random letters, one case (missed by a749023)
        "kemubcrdlsbq-gbcnnchcrnbs-dhuusbssmbhb",
        "xkqvbzrtwplm_hjgfdsnmcvbx",
        "QWRTPLKMNBVC-ZXCVBNMLKJHG-PLKMNBVCXZQW",
        "temizlik-kemubcrdlsbq-hizmet-gbcnnchc",  # one random segment among words
    ],
)
def test_08e_6_real_secret_shapes_are_still_caught(token):
    assert [f.category for f in find_secrets(f"anahtar {token} burada")] == ["API_TOKEN"], token
