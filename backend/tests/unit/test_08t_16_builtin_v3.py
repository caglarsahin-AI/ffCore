"""08 tam 1b, dilim 3 (K-08T1B-0004 A): built-in policy v3 and GUARDRAIL_EGRESS_NER.

The egress rule of the built-in policy reads its own PII policy, `default-egress`: with
GUARDRAIL_EGRESS_NER=true it is the regex identifiers plus person names (`engine: ner`), with
false the regex identifiers only (v2's egress). The text stages never call NER. True without
NER_MODEL / NER_REVISION stops the start-up; the external agent path checks egress with the
same policy (FacadeGuard).
"""

import asyncio

import pytest

from ffcore.guardrails import builtin, engine, service
from ffcore.guardrails.findings import Finding
from ffcore.guardrails.masking import MemoryTokenStore
from ffcore.guardrails.schemas import validate_pii_policy, validate_policy
from ffcore.guardrails.settings import GuardrailSettings, check_egress_ner


class FakeNer:
    model, revision = "acme/turkish-ner", "0123456789abcdef"

    def __init__(self):
        self.calls = 0

    async def find(self, text, categories):
        self.calls += 1
        start = text.find("Ayşe Demir")
        return (
            [] if start == -1 else [Finding("PERSON", start, start + 10, 0.97, "ner", "Ayşe Demir")]
        )


def policy(egress_ner: bool):
    return builtin.builtin_default(egress_ner)


def run(text, stage, pol, client):
    ctx = engine.EvalContext(
        run_id="r1", token_store=MemoryTokenStore(), egress_enabled=True, ner=client
    )
    return asyncio.run(engine.evaluate(text, stage, pol, ctx=ctx))


def test_08t_16_builtin_v3_person_tokenized():
    assert builtin.BUILTIN_VERSION == 3
    pol = policy(True)
    validate_policy(pol.spec, set(pol.pii_policies))
    for spec in pol.pii_policies.values():
        validate_pii_policy(spec)
    egress = pol.pii_policies[builtin.EGRESS_PII_KEY]
    assert egress.engine == "ner" and "PERSON" in egress.categories
    client = FakeNer()
    decision = run("Ayşe Demir 0532 123 45 67 arar.", "egress", pol, client)
    assert decision.text_out == "<<PII_1>> <<PII_2>> arar."
    assert client.calls == 1


def test_08t_16b_egress_ner_false_is_v2_egress():
    pol = policy(False)
    assert pol.pii_policies[builtin.EGRESS_PII_KEY] == builtin.DEFAULT_PII
    client = FakeNer()
    decision = run("Ayşe Demir 0532 123 45 67 arar.", "egress", pol, client)
    assert decision.text_out == "Ayşe Demir <<PII_1>> arar." and client.calls == 0


@pytest.mark.parametrize("stage", ["input.pre", "output.pre", "tool.post"])
def test_08t_16c_text_stages_never_call_ner(stage):
    client = FakeNer()
    run("Ayşe Demir 0532 123 45 67", stage, policy(True), client)
    assert client.calls == 0


def test_08t_16d_resolve_follows_the_setting(monkeypatch):
    async def none(*args, **kwargs):
        return None

    monkeypatch.setattr(service, "stored_policy", none)
    monkeypatch.setattr(service, "stored_pii", none)
    for flag, engine_name in ((True, "ner"), (False, "regex")):
        monkeypatch.setattr(
            service,
            "get_guardrail_settings",
            lambda flag=flag: GuardrailSettings(
                guardrail_egress_enabled=True, guardrail_egress_ner=flag
            ),
        )
        resolved = asyncio.run(service.resolve_policy(None, "p", builtin.BUILTIN_KEY))
        assert resolved.pii_policies[builtin.EGRESS_PII_KEY].engine == engine_name


class _Core:
    def __init__(self, model=None, revision=None):
        self.ner_model, self.ner_revision = model, revision


def test_08t_16e_egress_ner_without_model_stops_startup():
    on = GuardrailSettings(guardrail_egress_enabled=True, guardrail_egress_ner=True)
    with pytest.raises(RuntimeError) as raised:
        check_egress_ner(on, _Core())
    assert "ner_not_configured" in str(raised.value)
    check_egress_ner(on, _Core("acme/turkish-ner", "0123456789abcdef"))
    # Egress off (airgap) or NER off: nothing is needed.
    check_egress_ner(
        GuardrailSettings(guardrail_egress_enabled=False, guardrail_egress_ner=True), _Core()
    )
    check_egress_ner(
        GuardrailSettings(guardrail_egress_enabled=True, guardrail_egress_ner=False), _Core()
    )


def test_08t_16f_setting_has_no_default(monkeypatch):
    monkeypatch.delenv("GUARDRAIL_EGRESS_NER", raising=False)
    monkeypatch.setenv("GUARDRAIL_EGRESS_ENABLED", "true")
    with pytest.raises(ValueError):
        GuardrailSettings()


def test_08t_16g_external_agent_egress_uses_the_same_policy(monkeypatch):
    from ffcore.services import facade_guard

    client = FakeNer()
    monkeypatch.setattr(facade_guard, "local_ner", lambda: client)
    monkeypatch.setattr(
        facade_guard,
        "get_guardrail_settings",
        lambda: GuardrailSettings(guardrail_egress_enabled=True, guardrail_egress_ner=True),
    )
    monkeypatch.setattr(facade_guard, "RedisTokenStore", lambda redis, ttl: MemoryTokenStore())
    monkeypatch.setattr(facade_guard, "record_events", lambda *args, **kwargs: None)

    class Session:
        async def commit(self):
            pass

    guard = facade_guard.FacadeGuard(Session(), None, policy(True), "p")
    out = asyncio.run(guard.text("egress", "Ayşe Demir geldi"))
    assert out == "<<PII_1>> geldi" and client.calls == 1
