"""14: the memory PII check (brief 14 "Yazma" 3 and 6, C19; K-14-0003): fixed `block` policy in
code, the project's categories plus person names, placeholders refused, every refusal recorded."""

import asyncio

import pytest

from ffcore.guardrails.findings import Finding
from ffcore.memory import pii

TC = "13648065508"


class FakeNer:
    model, revision = "acme/turkish-ner", "0123456789abcdef"

    def __init__(self):
        self.calls = 0

    async def find(self, text, categories):
        self.calls += 1
        start = text.find("Kumbayır")
        return [] if start == -1 else [Finding("PERSON", start, start + 8, 0.97, "ner", "Kumbayır")]


class FakeSession:
    def __init__(self):
        self.added = []

    def add(self, row):
        self.added.append(row)


@pytest.fixture
def ner(monkeypatch):
    client = FakeNer()
    monkeypatch.setattr(pii, "ner_client", lambda: client)

    async def no_stored(session, project_id, key):
        return None

    monkeypatch.setattr(pii, "stored_pii", no_stored)
    return client


def check(text):
    session = FakeSession()
    outcome = asyncio.run(
        pii.check_memory_text(session, "00000000-0000-0000-0000-000000000001", text)
    )
    return outcome, session.added


def test_14_policy_is_block_enforce_with_person_names(ner):
    policy = asyncio.run(pii.memory_policy(FakeSession(), "p"))
    (rule,) = policy.spec.rules
    assert (rule.type, rule.action, rule.stages, policy.spec.mode) == (
        "pii",
        "block",
        ["input.pre"],
        "enforce",
    )
    spec = policy.pii_policies["memory"]
    assert spec.engine == "ner" and spec.categories["PERSON"].enabled
    assert spec.categories["TR_NATIONAL_ID"].enabled


@pytest.mark.parametrize(
    ("text", "category"),
    [(f"TC kimlik numaram {TC}", "TR_NATIONAL_ID"), ("Hasta Kaan Kumbayır yatıyor", "PERSON")],
)
def test_14_personal_data_is_blocked_and_recorded(ner, text, category):
    outcome, added = check(text)
    assert outcome.blocked and outcome.reason == "pii" and category in outcome.categories
    assert outcome.reference_id
    assert added and all(r.policy_key == "memory" and r.action_taken == "block" for r in added)
    assert all(
        TC not in str(r.input_preview) and "Kumbayır" not in str(r.input_preview) for r in added
    )


def test_14_clean_text_passes_without_a_record(ner):
    outcome, added = check("Tabloları TL cinsinden isterim.")
    assert not outcome.blocked and added == []
    assert ner.calls == 1


def test_14_placeholder_is_refused_and_recorded_without_the_engine(ner):
    outcome, added = check("Numarası <<PII_3>>.")
    assert outcome.blocked and outcome.reason == "placeholder"
    assert ner.calls == 0
    ((row,),) = [added]
    assert row.findings[0]["category"] == "egress_placeholder" and row.policy_key == "memory"


def test_14_without_ner_the_check_fails_loudly(monkeypatch):
    from ffcore.guardrails.schemas import GuardrailConfigError

    monkeypatch.setattr(pii, "ner_client", lambda: None)

    async def no_stored(session, project_id, key):
        return None

    monkeypatch.setattr(pii, "stored_pii", no_stored)
    with pytest.raises(GuardrailConfigError) as raised:
        check("Tabloları TL cinsinden isterim.")
    assert raised.value.code == "ner_not_configured"
