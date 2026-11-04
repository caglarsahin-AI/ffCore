"""08 tam 1b, dilim 1: the Turkish NER recognizer with a fake pipeline (no weights).

The real model is measured in `-m models` tests once `make models` has run (K-08T1B-0002);
here: label mapping, the `engine: ner` policy, regex findings that NER never overrides, the
worker's HTTP client and the fail-closed paths.
"""

import asyncio
import socket

import pytest

from ffcore.guardrails import engine
from ffcore.guardrails.masking import MemoryTokenStore
from ffcore.guardrails.recognizers import ner
from ffcore.guardrails.schemas import (
    GuardrailConfigError,
    PiiPolicySpec,
    ResolvedPolicy,
    validate_pii_policy,
)


def fake_pipeline(entities):
    def run(text):
        out = []
        for word, group, score in entities:
            start = text.find(word)
            if start != -1:
                out.append(
                    {
                        "entity_group": group,
                        "score": score,
                        "start": start,
                        "end": start + len(word),
                        "word": word,
                    }
                )
        return out

    return run


LABELS = {0: "O", 1: "B-PER", 2: "I-PER", 3: "B-ORG", 4: "I-ORG", 5: "B-LOC", 6: "I-LOC"}


def recognizer(entities, labels=LABELS):
    return ner.NerRecognizer(
        "acme/turkish-ner", "0123456789abcdef", pipeline=fake_pipeline(entities), labels=labels
    )


class FakeClient:
    model = "acme/turkish-ner"

    def __init__(self, rec=None, error=None):
        self.rec, self.error, self.calls = rec, error, 0

    async def find(self, text, categories):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.rec.recognize(text, categories)


def pii_policy(engine_name="ner", categories=("PERSON",), action="tokenize", **extra):
    cats = {code: {"enabled": True, "action": action} for code in categories}
    return PiiPolicySpec.model_validate({"engine": engine_name, "categories": cats, **extra})


def resolved(pii, *, on_error="block", stages=("egress",)):
    from ffcore.guardrails.schemas import PolicySpec

    spec = PolicySpec.model_validate(
        {
            "mode": "enforce",
            "on_error": on_error,
            "rules": [{"type": "pii", "pii_policy_key": "p", "stages": list(stages)}],
        }
    )
    return ResolvedPolicy(key="t", spec=spec, pii_policies={"p": pii}, builtin=False)


def run(text, policy, client):
    ctx = engine.EvalContext(
        run_id="r1", token_store=MemoryTokenStore(), egress_enabled=True, ner=client
    )
    return asyncio.run(engine.evaluate(text, "egress", policy, ctx=ctx))


def test_08t_17_engine_ner_accepted():
    validate_pii_policy(pii_policy("ner", ("PERSON", "ORGANIZATION", "LOCATION", "TR_PHONE")))
    with pytest.raises(GuardrailConfigError) as raised:
        validate_pii_policy(pii_policy("regex", ("PERSON",)))
    assert raised.value.code == "category_unsupported"


def test_08t_17b_regex_engine_never_calls_ner():
    client = FakeClient(error=AssertionError("NER called under engine regex"))
    decision = run("Ara: 0532 123 45 67", resolved(pii_policy("regex", ("TR_PHONE",))), client)
    assert client.calls == 0
    assert "0532 123 45 67" not in decision.text_out


def test_08t_17c_ner_person_tokenized_with_evidence():
    client = FakeClient(recognizer([("Ayşe Demir", "PER", 0.98)]))
    decision = run("Sözleşmeyi Ayşe Demir imzaladı.", resolved(pii_policy()), client)
    assert decision.text_out == "Sözleşmeyi <<PII_1>> imzaladı."
    finding = decision.events[0].findings[0]
    assert finding["category"] == "PERSON"
    assert finding["evidence"] == "ner acme/turkish-ner@0123456 score 0.98"
    assert "Ayşe" not in str(decision.events[0].matches)


def test_08t_17d_category_filter_and_confidence():
    client = FakeClient(
        recognizer([("Ayşe Demir", "PER", 0.98), ("Ankara", "LOC", 0.99), ("Can", "PER", 0.4)])
    )
    pii = pii_policy(categories=("PERSON",), min_confidence=0.5)
    decision = run("Ayşe Demir Ankara'da, Can da orada.", resolved(pii), client)
    assert decision.text_out == "<<PII_1>> Ankara'da, Can da orada."


def test_08t_2b_ner_never_overrides_a_regex_finding():
    # A NER span that overlaps a checksummed regex value is dropped, whatever its score.
    phone = "0532 123 45 67"
    client = FakeClient(recognizer([("Demir 0532", "PER", 0.999)]))
    pii = pii_policy(categories=("PERSON", "TR_PHONE"), action="redact")
    decision = run(f"Ali Demir {phone}", resolved(pii), client)
    assert "[TR_PHONE]" in decision.text_out and phone not in decision.text_out
    assert [f["category"] for f in decision.events[0].findings] == ["TR_PHONE"]


def test_08t_5b_unknown_label_fails_at_load():
    with pytest.raises(ner.NerConfigError) as raised:
        recognizer([], labels={**LABELS, 7: "B-DISEASE"})
    assert raised.value.code == "ner_label_unknown" and "B-DISEASE" in str(raised.value)
    # Labels that carry no PII category are named, never guessed.
    rec = recognizer([], labels={0: "O", 1: "B-PER", 2: "B-MISC"})
    assert rec.ignored_labels == ("MISC",)


def test_08t_5_ner_missing_weights_fail_loud(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_HOME", str(tmp_path / "hf"))

    def no_network(*args, **kwargs):
        raise AssertionError("network request during a model load")

    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket, "getaddrinfo", no_network)
    from ffcore.knowledge.models import ModelMissing

    with pytest.raises(ModelMissing) as raised:
        ner.NerRecognizer.load("acme/turkish-ner", "0123456789abcdef")
    assert raised.value.name == "acme/turkish-ner"


def test_08t_5c_ner_not_configured_is_loud():
    with pytest.raises(GuardrailConfigError) as raised:
        run("Ayşe Demir", resolved(pii_policy()), None)
    assert raised.value.code == "ner_not_configured"
    for client in (ner.LocalNer(None, None), ner.HttpNer(_Unset())):
        with pytest.raises(ner.NerConfigError) as raised:
            asyncio.run(client.find("Ayşe Demir", ["PERSON"]))
        assert raised.value.code == "ner_not_configured"


class _Unset:
    ner_model = ner_revision = None
    internal_api_url = "http://backend:8000"


def test_08t_6b_ner_down_fails_closed():
    client = FakeClient(error=ner.NerUnavailable("internal ner failed: 503"))
    decision = run("Ayşe Demir 0532 123 45 67", resolved(pii_policy()), client)
    assert decision.action == "block" and decision.text_out == ""
    assert decision.events[0].error == "NerUnavailable"
    # on_error=allow records the failure; nothing is sent as if NER had run.
    decision = run("Ayşe Demir", resolved(pii_policy(), on_error="allow"), client)
    assert decision.events[0].status == "failed"


def test_08t_6_worker_uses_http_ner(monkeypatch):
    from ffcore.runtime import adapters

    seen = {}

    class Http:
        def __init__(self, settings):
            seen["http"] = True

    monkeypatch.setattr(ner, "HttpNer", Http)
    monkeypatch.setattr(
        ner, "local_ner", lambda: (_ for _ in ()).throw(AssertionError("model in the worker"))
    )
    guard = adapters.EngineGuard(
        None, None, None, None, run_id="r", project_id="p", egress_enabled=True, token_ttl_s=10
    )
    assert seen == {"http": True} and isinstance(guard._ner, Http)


def test_08t_6c_http_ner_rebuilds_values_and_checks_model(monkeypatch):
    from ffcore.core.config import get_settings

    calls = []

    class Response:
        status_code = 200

        def __init__(self, body):
            self._body = body

        def json(self):
            return self._body

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def request(self, method, url, headers=None, json=None):
            calls.append((method, url, json))
            return Response(
                {
                    "model": "acme/turkish-ner",
                    "revision": "0123456789abcdef",
                    "findings": [
                        {
                            "category": "PERSON",
                            "start": 4,
                            "end": 14,
                            "score": 0.97,
                            "evidence": "ner acme/turkish-ner@0123456 score 0.97",
                        }
                    ],
                }
            )

    from ffcore.core import egress

    monkeypatch.setattr(egress, "SafeOutboundClient", Client)
    monkeypatch.setattr(ner, "service_authorization", lambda s: {"Authorization": "x"})
    base = get_settings()
    settings = base.model_copy(
        update={
            "internal_api_url": "http://backend:8000",
            "ner_model": "acme/turkish-ner",
            "ner_revision": "0123456789abcdef",
        }
    )
    client = ner.HttpNer(settings)
    found = asyncio.run(client.find("Bay Ayşe Demir geldi", ["PERSON"]))
    assert calls[0][1] == "http://backend:8000/api/v1/internal/guardrails/ner"
    assert calls[0][2] == {"text": "Bay Ayşe Demir geldi", "categories": ["PERSON"]}
    assert found[0].value == "Ayşe Demir" and found[0].category == "PERSON"

    settings = base.model_copy(update={"ner_model": "other/model", "ner_revision": "x"})
    with pytest.raises(ner.NerUnavailable):
        asyncio.run(ner.HttpNer(settings).find("Bay Ayşe Demir geldi", ["PERSON"]))


def test_08t_6d_internal_ner_returns_spans_not_values(monkeypatch):
    from ffcore.api import guardrails as api
    from ffcore.core.errors import ApiError
    from ffcore.guardrails.api_schemas import NerRequest

    rec = recognizer([("Ayşe Demir", "PER", 0.97), ("Ankara", "LOC", 0.9)])
    client = ner.LocalNer("acme/turkish-ner", "0123456789abcdef", recognizer=rec)
    monkeypatch.setattr(api, "local_ner", lambda: client)
    body = NerRequest(text="Ayşe Demir Ankara'da", categories=["PERSON"])
    out = asyncio.run(api.internal_ner(body, actor=None))
    assert (out.model, out.revision) == ("acme/turkish-ner", "0123456789abcdef")
    assert [(f.category, f.start, f.end) for f in out.findings] == [("PERSON", 0, 10)]
    assert "Ayşe" not in out.model_dump_json()

    monkeypatch.setattr(api, "local_ner", lambda: ner.LocalNer(None, None))
    with pytest.raises(ApiError) as raised:
        asyncio.run(api.internal_ner(body, actor=None))
    assert raised.value.status_code == 503 and raised.value.code == "ner_not_configured"
