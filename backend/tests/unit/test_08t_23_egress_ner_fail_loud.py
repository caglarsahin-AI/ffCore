"""08 tam 1b r1 MINOR-1 (A): at egress a NER failure fails loudly whatever `on_error` says.

Probe E4: a stored `engine: ner` egress policy with `on_error: allow` sent the name and the
checksummed identifiers raw when NER was down. The regex mask of identifiers must not hang on an
HTTP dependency (the 1a f' precedent, PlaceholderOutOfRange). The text stages keep `on_error`.
"""

import asyncio

import pytest

from ffcore.guardrails import engine
from ffcore.guardrails.masking import MemoryTokenStore
from ffcore.guardrails.recognizers import ner
from ffcore.guardrails.schemas import PiiPolicySpec, PolicySpec, ResolvedPolicy

TEXT = "Ayşe Demir 10000000146 0532 123 45 67 ayse@ornek.com"


class DownNer:
    model, revision = "acme/turkish-ner", "0123456789abcdef"

    def __init__(self, error):
        self.error = error

    async def find(self, text, categories):
        raise self.error


def _policy(on_error, stage, mode="enforce"):
    pii = PiiPolicySpec.model_validate(
        {
            "engine": "ner",
            "default_action": "tokenize",
            "categories": {
                c: {"enabled": True}
                for c in ("PERSON", "TR_NATIONAL_ID", "TR_PHONE", "EMAIL_ADDRESS")
            },
        }
    )
    spec = PolicySpec.model_validate(
        {
            "mode": mode,
            "on_error": on_error,
            "rules": [{"type": "pii", "action": "tokenize" if stage == "egress" else "redact",
                       "pii_policy_key": "p", "stages": [stage]}],
        }
    )
    return ResolvedPolicy(key="t", spec=spec, pii_policies={"p": pii}, builtin=False)


def _run(policy, stage, client):
    ctx = engine.EvalContext(
        run_id="r1", token_store=MemoryTokenStore(), egress_enabled=True, ner=client
    )
    return asyncio.run(engine.evaluate(TEXT, stage, policy, ctx=ctx))


@pytest.mark.parametrize("on_error", ["allow", "log", "block"])
@pytest.mark.parametrize(
    "error", [ner.NerUnavailable("internal ner failed: 503"), RuntimeError("model gone")]
)
def test_08t_23_egress_ner_down_is_loud_whatever_on_error(on_error, error):
    with pytest.raises(ner.NerEgressUnavailable) as raised:
        _run(_policy(on_error, "egress"), "egress", DownNer(error))
    assert raised.value.status_code == 503 and raised.value.code == "ner_unavailable"
    assert "Ayşe" not in str(raised.value) and "10000000146" not in str(raised.value)


def test_08t_23b_text_stages_keep_on_error():
    decision = _run(_policy("allow", "input.pre"), "input.pre", DownNer(ner.NerUnavailable("x")))
    assert decision.events[0].status == "failed" and decision.action != "block"
    decision = _run(_policy("block", "input.pre"), "input.pre", DownNer(ner.NerUnavailable("x")))
    assert decision.action == "block"


def test_08t_23c_monitor_egress_rule_only_records():
    # A monitor rule masks nothing even when NER is up; its failure is recorded, not raised.
    decision = _run(
        _policy("allow", "egress", mode="monitor"), "egress", DownNer(ner.NerUnavailable("x"))
    )
    assert decision.events[0].status == "failed"
