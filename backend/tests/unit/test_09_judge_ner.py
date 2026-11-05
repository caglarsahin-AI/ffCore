"""09-1 r1 MINOR-9 (after 08 tam 1b): the judge's egress guard carries the worker's NER client.

With GUARDRAIL_EGRESS_NER=true the built-in egress PII policy is `engine: ner` with PERSON
(08 tam 1b v3). A guard without a NER client fails that policy loudly (`ner_not_configured`),
so every judged item would be a `judge_failed` error; with one, a name in the answer is masked
before it reaches the judge model. Workers never load the model: `HttpNer` asks the API.
"""

import asyncio
import uuid
from types import SimpleNamespace

import pytest

from ffcore.evaluation import judge as judge_mod
from ffcore.evaluation import worker_tick
from ffcore.guardrails import builtin, service
from ffcore.guardrails.findings import Finding
from ffcore.guardrails.masking import MemoryTokenStore
from ffcore.guardrails.recognizers.ner import HttpNer
from ffcore.guardrails.settings import GuardrailSettings

NAME = "Ayşe Yılmaz"
TEXT = f"Hastanın sorumlu hekimi {NAME} olarak kayıtlı."


class FakeNer:
    model = "fake-ner"

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple]] = []

    async def find(self, text, categories):
        self.calls.append((text, tuple(sorted(categories))))
        start = text.find(NAME)
        if start < 0 or "PERSON" not in categories:
            return []
        return [Finding("PERSON", start, start + len(NAME), 0.99, "fake ner", NAME)]


class FakeSession:
    def __init__(self) -> None:
        self.added = []

    def add(self, row) -> None:
        self.added.append(row)


def _egress_ner_on(monkeypatch):
    async def nothing_stored(*args, **kwargs):
        return None

    monkeypatch.setattr(service, "stored_pii", nothing_stored)
    monkeypatch.setattr(service, "stored_policy", nothing_stored)
    monkeypatch.setattr(
        service,
        "get_guardrail_settings",
        lambda: GuardrailSettings(guardrail_egress_enabled=True, guardrail_egress_ner=True),
    )
    return asyncio.run(service.resolve_policy(None, "p", builtin.BUILTIN_KEY))


def _guard(session, policy, ner):
    guard = judge_mod.EgressGuard(
        session,
        None,
        policy,
        run_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        egress_enabled=True,
        ttl_s=60,
        ner=ner,
    )
    guard._tokens = MemoryTokenStore()
    return guard


def test_09_judge_egress_masks_a_name_with_egress_ner(monkeypatch):
    policy = _egress_ner_on(monkeypatch)
    assert policy.pii_policies[builtin.EGRESS_PII_KEY].engine == "ner"
    ner, session = FakeNer(), FakeSession()
    action, text = asyncio.run(_guard(session, policy, ner).egress(TEXT))
    assert NAME not in text and "<<PII_" in text
    assert action != "block"
    assert ner.calls and "PERSON" in ner.calls[0][1]
    assert session.added, "the masking is recorded as guardrail events"


def test_09_judge_egress_without_ner_client_fails_loudly(monkeypatch):
    policy = _egress_ner_on(monkeypatch)
    with pytest.raises(Exception) as caught:
        asyncio.run(_guard(FakeSession(), policy, None).egress(TEXT))
    assert "ner_not_configured" in f"{getattr(caught.value, 'code', '')} {caught.value}"


def test_09_worker_judge_guard_gets_the_http_ner(monkeypatch):
    captured = {}

    class Stop(Exception):
        pass

    class CapturingGuard:
        def __init__(self, *args, **kwargs):
            captured.update(kwargs)
            raise Stop

    class Session:
        async def get(self, model, key):
            return SimpleNamespace(definition={})

    async def policy(*args, **kwargs):
        return None

    monkeypatch.setattr(
        worker_tick, "parse_definition", lambda d: SimpleNamespace(guardrail_policy_key="default")
    )
    monkeypatch.setattr(worker_tick, "resolve_policy", policy)
    monkeypatch.setattr(worker_tick.judge_mod, "EgressGuard", CapturingGuard)
    settings = SimpleNamespace(eval_judge_model="judge", ner_model="m", ner_revision="r")
    run_judge = worker_tick._judge(settings, Session(), None, None, None)
    run = SimpleNamespace(agent_version_id=uuid.uuid4(), id=uuid.uuid4(), project_id=uuid.uuid4())
    with pytest.raises(Stop):
        asyncio.run(run_judge(run, {}, None, {}))
    assert isinstance(captured["ner"], HttpNer)
    assert (captured["ner"].model, captured["ner"].revision) == ("m", "r")
