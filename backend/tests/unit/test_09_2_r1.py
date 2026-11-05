"""09-2 r1 (KARARLAR "09-2 r1 kararları"): the unit side of the review's corrections.

MAJOR-1: an exam records the digest of the definition it examines (`definition_sha256`) and a
queued exam whose definition changed before its item runs started ends
`failed(definition_changed)`. MINOR-6/7: the judge tells an NER misconfiguration from an outage
by the API's error code (and the HTTP status), never by the text of a message.
"""

import asyncio
import hashlib
import json

import anyio
import pytest

from ffcore.core import egress
from ffcore.evaluation import judge as judge_mod
from ffcore.guardrails.recognizers import ner
from tests.unit.test_09_engine import _start_eval, _start_items, _version
from tests.unit.test_09_judge_ner import TEXT, FakeSession, _egress_ner_on, _guard
from tests.unit.test_09_r3 import _NeverCalled, _Rubric


def _digest(definition: dict) -> str:
    text = json.dumps(definition, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode()).hexdigest()


# --- MAJOR-1 ----------------------------------------------------------------------------------


def test_09_2_r1_major1_exam_records_the_examined_definition(monkeypatch):
    _, go = _start_eval(monkeypatch)
    ev = anyio.run(go)
    assert ev.config["definition_sha256"] == _digest(_version().definition)


def test_09_2_r1_major1_digest_ignores_key_order():
    from ffcore.evaluation.gate import definition_sha256

    assert definition_sha256({"a": 1, "b": [1, 2]}) == definition_sha256({"b": [1, 2], "a": 1})
    assert definition_sha256({"a": 1}) == _digest({"a": 1})
    assert definition_sha256({"a": 1}) != definition_sha256({"a": 2})


def test_09_2_r1_major1_queued_exam_with_a_changed_definition_starts_nothing(monkeypatch):
    from ffcore.evaluation import runner

    ev, session, started = _start_items(monkeypatch)
    ev.config["definition_sha256"] = _digest({"model": "examined", "system_prompt": "before"})
    anyio.run(lambda: runner.start_items(session, None, ev, queue=None, queued_event=None))
    assert started == []
    assert (ev.status, ev.error_code) == ("failed", "definition_changed")
    assert ev.ended_at is not None


# --- MINOR-6/7: NER failures are told apart by code -------------------------------------------


def _settings():
    from ffcore.core.config import get_settings

    return get_settings().model_copy(
        update={
            "internal_api_url": "http://backend:8000",
            "ner_model": "acme/turkish-ner",
            "ner_revision": "0123456789abcdef",
        }
    )


def _answering(status: int, body: dict):
    class Response:
        status_code = status

        def json(self):
            return body

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def request(self, *args, **kwargs):
            return Response()

    return Client


def _find(monkeypatch, status, body):
    monkeypatch.setattr(egress, "SafeOutboundClient", _answering(status, body))
    monkeypatch.setattr(ner, "service_authorization", lambda s: {"Authorization": "x"})
    with pytest.raises(ner.NerUnavailable) as err:
        asyncio.run(ner.HttpNer(_settings()).find("Bay Ayşe Demir", ["PERSON"]))
    return err.value


def _error(code):
    return {"error": {"message": "m", "type": "api_error", "code": code}}


@pytest.mark.parametrize(
    "status,body,code",
    [
        (503, _error("ner_not_configured"), "ner_not_configured"),
        (503, _error("model_missing"), "model_missing"),
        (401, _error("invalid_token"), "invalid_token"),
        (502, {"detail": "bad gateway"}, None),  # no FFCore error body: no code
    ],
)
def test_09_2_r1_minor6_http_ner_carries_the_apis_code(monkeypatch, status, body, code):
    exc = _find(monkeypatch, status, body)
    assert (exc.status, exc.code) == (status, code)


def test_09_2_r1_minor7_model_mismatch_has_a_code(monkeypatch):
    body = {"model": "other/ner", "revision": "1", "findings": []}
    exc = _find(monkeypatch, 200, body)
    assert exc.code == "ner_model_mismatch"


class _NerFails:
    model = "fake-ner"

    def __init__(self, message, **kw):
        self.message, self.kw = message, kw

    async def find(self, text, categories):
        raise ner.NerUnavailable(self.message, **self.kw)


def _judge(monkeypatch, message, **kw):
    policy = _egress_ner_on(monkeypatch)
    guard = _guard(FakeSession(), policy, _NerFails(message, **kw))
    return anyio.run(
        lambda: judge_mod.judge(
            question="q", expected="e", answer=TEXT, rubric=_Rubric(), guard=guard,
            model=_NeverCalled(), pass_min=4,
        )
    )  # fmt: skip


@pytest.mark.parametrize(
    "kw",
    [
        {"status": 503, "code": "ner_not_configured"},
        {"status": 503, "code": "model_missing"},
        {"status": 503, "code": "ner_label_unknown"},
        {"status": 503, "code": "ner_offsets_unavailable"},
        {"status": 200, "code": "ner_model_mismatch"},
        {"status": 401, "code": "invalid_token"},  # the API refuses the worker: configuration
        {"status": 422, "code": None},
    ],
)
def test_09_2_r1_minor6_misconfiguration_by_code_fails_loudly(monkeypatch, kw):
    with pytest.raises(judge_mod.NerMisconfigured):
        _judge(monkeypatch, "internal ner failed", **kw)


@pytest.mark.parametrize(
    "kw",
    [
        {"status": 503, "code": "api_error"},
        {"status": 502, "code": None},
        {"status": None, "code": None},  # no answer at all (refused, DNS, timeout)
    ],
)
def test_09_2_r1_minor6_outage_by_code_stays_not_run(monkeypatch, kw):
    score = _judge(monkeypatch, "internal ner failed", **kw).score
    assert (score.status, score.comment) == ("not_run", "ner_unavailable")


def test_09_2_r1_minor7_message_text_alone_decides_nothing(monkeypatch):
    # The 09-2 text match is gone: a message that reads like a 4xx, without a code or status,
    # is an outage like any NerUnavailable without one.
    for message in ("internal ner failed: 401", "API runs NER x@1, worker expects y@2"):
        score = _judge(monkeypatch, message).score
        assert score.comment == "ner_unavailable", message


def test_09_2_r1_minor6_worker_maps_unknown_cause_to_outage():
    # A NerEgressUnavailable without a NerUnavailable cause (another exception) is an outage.
    exc = ner.NerEgressUnavailable("RuntimeError")
    assert judge_mod.ner_failure(exc) == "ner_unavailable"
    exc.__cause__ = ner.NerUnavailable("x", status=503, code="model_missing")
    assert judge_mod.ner_failure(exc) == "ner_misconfigured"


# --- live probe: the from-run answer says how the item was masked -------------------------------


def test_09_2_r1_masking_names_ner_only_when_an_egress_pii_rule_uses_it():
    from ffcore.evaluation.from_run import masking_of
    from ffcore.guardrails.schemas import PiiPolicySpec, PolicySpec, ResolvedPolicy, Rule

    def policy(stages, engine):
        rule = Rule(type="pii", stages=stages, pii_policy_key="p")
        return ResolvedPolicy("k", PolicySpec(rules=[rule]), {"p": PiiPolicySpec(engine=engine)})

    assert masking_of(policy(["egress"], "regex")) == "regex"
    assert masking_of(policy(["egress"], "ner")) == "regex+ner"
    assert masking_of(policy(["input.pre"], "ner")) == "regex"  # NER, but not at egress
