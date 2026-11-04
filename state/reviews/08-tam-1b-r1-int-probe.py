"""Reviewer probe for 08-tam-1b r1 (f6be9ae): the internal NER endpoint over HTTP (auth, body
limits, spans only), `engine: ner` through the public API, /guardrails/test without a model.
Mounted as backend/tests/integration/test_zz_08t1b_probe.py in the tools container.
"""

import uuid

import pytest

from tests.dummy import SERVICE_TOKEN

SVC = {"Authorization": f"Bearer {SERVICE_TOKEN}"}
PATHS = ("/api/v1/internal/guardrails/ner", "/internal/guardrails/ner")


class FakeRec:
    model, revision = "acme/turkish-ner", "0123456789abcdef"

    def recognize(self, text, categories):
        from ffcore.guardrails.findings import Finding

        out = []
        for name in ("Ayşe Demir", "Mehmet Kaya"):
            at = text.find(name)
            if at != -1 and "PERSON" in categories:
                out.append(Finding("PERSON", at, at + len(name), 0.97, "ner acme score 0.97", name))
        return out


@pytest.fixture
def fake_ner(monkeypatch):
    from ffcore.api import guardrails as api
    from ffcore.guardrails.recognizers import ner

    client = ner.LocalNer("acme/turkish-ner", "0123456789abcdef", recognizer=FakeRec())
    monkeypatch.setattr(api, "local_ner", lambda: client)
    return client


@pytest.mark.parametrize("path", PATHS)
def test_zz_ner_auth(client_factory, make_user, path):
    _, email = make_user(superadmin="edit")
    body = {"text": "Ayşe Demir", "categories": ["PERSON"]}
    anon = client_factory().post(path, json=body)
    user = client_factory(email).post(path, json=body)
    bogus = client_factory().post(path, json=body, headers={"Authorization": "Bearer nope"})
    svc = client_factory().post(path, json=body, headers=SVC)
    print(f"PROBE auth {path}: anon={anon.status_code} superadmin={user.status_code} "
          f"{user.json().get('error', {}).get('code') if user.status_code < 500 else ''} "
          f"bogus={bogus.status_code} service(no model)={svc.status_code} {svc.text[:160]}")


def test_zz_ner_spans_only_and_limits(client_factory, fake_ner):
    c = client_factory()
    ok = c.post(PATHS[0], json={"text": "Bay Ayşe Demir ve Mehmet Kaya", "categories": ["PERSON"]}, headers=SVC)
    print(f"PROBE spans: {ok.status_code} {ok.text}")
    print(f"PROBE value-in-body: {'Ayşe' in ok.text or 'Kaya' in ok.text}")
    for name, body in {
        "200001 chars": {"text": "a" * 200_001, "categories": ["PERSON"]},
        "200000 chars": {"text": "a" * 200_000, "categories": ["PERSON"]},
        "no categories": {"text": "x", "categories": []},
        "bad category": {"text": "x", "categories": ["EMAIL_ADDRESS"]},
        "extra field": {"text": "x", "categories": ["PERSON"], "url": "http://evil"},
    }.items():
        r = c.post(PATHS[0], json=body, headers=SVC)
        print(f"PROBE limit {name}: {r.status_code} {r.text[:120]}")


def test_zz_engine_ner_public_api(client_factory, make_user, make_project):
    _, email = make_user(superadmin="edit")
    c = client_factory(email)
    project = make_project()
    key = f"ner-{uuid.uuid4().hex[:6]}"
    r = c.post(
        f"/api/v1/projects/{project}/pii-policies",
        json={"key": key, "name": "NER", "engine": "ner", "default_action": "tokenize",
              "categories": {"PERSON": {"enabled": True}}},
    )
    print(f"PROBE create engine ner: {r.status_code} {r.text[:160]}")
    pol = c.post(
        f"/api/v1/projects/{project}/guardrail-policies",
        json={"key": f"g-{key}", "name": "G", "mode": "enforce",
              "rules": [{"type": "pii", "pii_policy_key": key, "stages": ["input.pre"]}]},
    )
    print(f"PROBE policy: {pol.status_code} {pol.text[:160]}")
    t = c.post(
        f"/api/v1/projects/{project}/guardrails/test",
        json={"text": "Ayşe Demir geldi", "stage": "input.pre", "policy_key": f"g-{key}"},
    )
    print(f"PROBE /guardrails/test engine ner without model: {t.status_code} {t.text[:200]}")
    lst = c.get(f"/api/v1/projects/{project}/guardrail-policies")
    print(f"PROBE builtin listing: {lst.status_code} "
          f"{[(p.get('key'), p.get('builtin_version')) for p in lst.json().get('items', lst.json() if isinstance(lst.json(), list) else [])]}")
    pii = c.get(f"/api/v1/projects/{project}/pii-policies")
    print(f"PROBE pii listing keys: {[p.get('key') for p in pii.json().get('items', [])]}")
