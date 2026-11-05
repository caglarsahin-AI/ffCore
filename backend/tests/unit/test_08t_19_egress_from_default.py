"""08 tam 1b r1 MAJOR-1 (KARARLAR "08 tam 1b r1 kararları", A): the built-in egress PII policy is
derived from the project's stored `default` PII policy when there is no stored `default-egress`.

v2's egress rule read `default`, so a project's custom patterns and extra categories reached the
egress mask; v3 must not drop them silently. With GUARDRAIL_EGRESS_NER=true `PERSON` and
`engine: ner` are added; the built-in five are used only when neither key is stored.
"""

import asyncio
from types import SimpleNamespace

from ffcore.guardrails import builtin, engine, service
from ffcore.guardrails.masking import MemoryTokenStore
from ffcore.guardrails.settings import GuardrailSettings

STORED_DEFAULT = SimpleNamespace(
    engine="regex",
    default_action="redact",
    languages=["tr", "en"],
    min_confidence=0.0,
    context_boost=True,
    categories={"TR_TAX_ID": {"enabled": True, "severity": "high"}, "TR_PHONE": {"enabled": True}},
    custom_patterns=[
        {"name": "vkn", "category": "TR_TAX_ID", "pattern": r"(?<!\d)\d{10}(?!\d)", "score": 0.95}
    ],
)


def _patch(monkeypatch, stored: dict, egress_ner: bool):
    async def stored_pii(session, project_id, key):
        return stored.get(key)

    async def no_policy(*args, **kwargs):
        return None

    monkeypatch.setattr(service, "stored_pii", stored_pii)
    monkeypatch.setattr(service, "stored_policy", no_policy)
    monkeypatch.setattr(
        service,
        "get_guardrail_settings",
        lambda: GuardrailSettings(guardrail_egress_enabled=True, guardrail_egress_ner=egress_ner),
    )


def _egress(monkeypatch, stored, egress_ner):
    _patch(monkeypatch, stored, egress_ner)
    resolved = asyncio.run(service.resolve_policy(None, "p", builtin.BUILTIN_KEY))
    return resolved, resolved.pii_policies[builtin.EGRESS_PII_KEY]


def test_08t_19_stored_default_custom_pattern_tokenized_at_egress(monkeypatch):
    resolved, egress = _egress(monkeypatch, {"default": STORED_DEFAULT}, False)
    assert egress.engine == "regex" and "PERSON" not in egress.categories
    ctx = engine.EvalContext(run_id="r1", token_store=MemoryTokenStore(), egress_enabled=True)
    decision = asyncio.run(engine.evaluate("VKN 1234567890 sorulur", "egress", resolved, ctx=ctx))
    assert decision.text_out == "VKN <<PII_1>> sorulur"


def test_08t_19b_egress_ner_adds_person_to_the_stored_default(monkeypatch):
    _, egress = _egress(monkeypatch, {"default": STORED_DEFAULT}, True)
    assert egress.engine == "ner"
    assert egress.categories["PERSON"].enabled
    assert egress.categories["TR_TAX_ID"].enabled
    assert [p.name for p in egress.custom_patterns] == ["vkn"]


def test_08t_19c_stored_default_egress_wins(monkeypatch):
    own = SimpleNamespace(**{**vars(STORED_DEFAULT), "custom_patterns": []})
    _, egress = _egress(monkeypatch, {"default": STORED_DEFAULT, "default-egress": own}, True)
    assert egress.custom_patterns == [] and egress.engine == "regex"


def test_08t_19d_nothing_stored_is_the_builtin(monkeypatch):
    _, egress = _egress(monkeypatch, {}, True)
    assert egress == builtin.DEFAULT_EGRESS_PII_NER
    _, egress = _egress(monkeypatch, {}, False)
    assert egress == builtin.DEFAULT_PII
