"""Reviewer probe for 08-tam-1b r2 (4567ed6): r1 MAJOR-1 (a stored `default` PII policy with a
custom pattern still tokenizes at egress through the built-in chain), r1 MINOR-4 (the built-in
policy as GET returns it can be stored back; test panel reports the built-in egress PII), and the
r1 HTTP authorization probe of the internal NER endpoint.
Mounted as backend/tests/integration/test_zz_08t1b_r2_probe.py in the tools container.
"""

import uuid

from tests.dummy import SERVICE_TOKEN

SVC = {"Authorization": f"Bearer {SERVICE_TOKEN}"}
PLATE = "34 ABC 123"


def _setup(client_factory, make_user, make_project):
    _, email = make_user(superadmin="edit")
    c = client_factory(email)
    return c, make_project()


def test_zz_major1_stored_default_custom_pattern_at_egress(client_factory, make_user, make_project):
    c, project = _setup(client_factory, make_user, make_project)
    r = c.post(
        f"/api/v1/projects/{project}/pii-policies",
        json={
            "key": "default",
            "name": "Project default",
            "default_action": "redact",
            "categories": {"TR_PLATE": {"enabled": True}, "EMAIL_ADDRESS": {"enabled": True}},
            "custom_patterns": [
                {"name": "plate", "category": "TR_PLATE", "pattern": r"\b34 [A-Z]{3} \d{3}\b"}
            ],
        },
    )
    print(f"PROBE stored default: {r.status_code} {r.text[:120]}")
    svc = client_factory()
    for stage in ("egress", "input.pre"):
        ev = svc.post(
            "/api/v1/internal/guardrails/evaluate",
            headers=SVC,
            json={
                "project_id": str(project),
                "stage": stage,
                "text": f"Araç {PLATE}, e-posta a.b@ornek.com",
                "policy_key": "default",
                "run_id": str(uuid.uuid4()),
            },
        )
        body = ev.json() if ev.status_code < 500 else {}
        out = body.get("text_out", "")
        print(f"PROBE {stage} built-in chain with stored default: {ev.status_code} "
              f"action={body.get('action')} plate_raw={PLATE in out} out={out!r}")


def test_zz_minor4_builtin_spec_round_trip(client_factory, make_user, make_project):
    c, project = _setup(client_factory, make_user, make_project)
    got = c.get(f"/api/v1/projects/{project}/guardrail-policies")
    body = got.json()
    items = body.get("data", body.get("items", []))
    builtin = next((p for p in items if p.get("builtin")), None)
    print(f"PROBE GET builtin: {got.status_code} key={builtin and builtin.get('key')} "
          f"version={builtin and builtin.get('builtin_version')}")
    if builtin is None:
        print(f"PROBE GET body: {got.text[:300]}")
        return
    rules = builtin["rules"]
    post = c.post(
        f"/api/v1/projects/{project}/guardrail-policies",
        json={"key": "default", "name": "Stored built-in", "mode": "enforce", "rules": rules},
    )
    print(f"PROBE POST built-in rules as stored default: {post.status_code} {post.text[:160]}")
    pii = c.get(f"/api/v1/projects/{project}/pii-policies")
    pbody = pii.json()
    keys = [(p.get("key"), p.get("builtin")) for p in pbody.get("data", pbody.get("items", []))]
    print(f"PROBE PII listing: {keys}")
    panel = c.post(
        f"/api/v1/projects/{project}/guardrails/test",
        json={"text": "a.b@ornek.com", "stage": "egress", "policy_key": "default-egress", "action": "tokenize"},
    )
    print(f"PROBE test panel default-egress: {panel.status_code} builtin={panel.json().get('builtin') if panel.status_code < 500 else None}")


def test_zz_ner_auth_http(client_factory, make_user):
    _, email = make_user(superadmin="edit")
    body = {"text": "Ayşe Demir", "categories": ["PERSON"]}
    path = "/api/v1/internal/guardrails/ner"
    anon = client_factory().post(path, json=body)
    user = client_factory(email).post(path, json=body)
    svc = client_factory().post(path, json=body, headers=SVC)
    print(f"PROBE NER auth: anon={anon.status_code} superadmin={user.status_code} service={svc.status_code} {svc.text[:100]}")
