"""08 tam 1b r1 MINOR-4: `default-egress` is an available PII key, listed as built-in.

Before: the built-in chain showed `pii_policy_key: default-egress`, but storing that chain as it
was gave 422 `pii_policy_not_found`; the easy way out (pointing egress at `default`) dropped the
person-name mask without a [C] decision. The test panel reported the built-in egress PII as
`builtin: false`.
"""

import pytest

from tests.integration.test_08_api import P, admin, project  # noqa: F401  (fixtures)


@pytest.fixture
def base(project):  # noqa: F811
    return P.format(project)


def test_08t_26_builtin_chain_stores_as_shown(admin, base):  # noqa: F811
    listed = admin.get(base + "/pii-policies").json()["data"]
    builtins = {p["key"]: p for p in listed if p["builtin"]}
    assert set(builtins) == {"default", "default-egress"}, listed
    assert builtins["default-egress"]["id"] is None

    chain = admin.get(base + "/guardrail-policies").json()["data"][0]
    assert chain["builtin"] and any(
        r.get("pii_policy_key") == "default-egress" for r in chain["rules"]
    )
    body = {
        "key": "default",
        "name": "Stored copy of the built-in",
        "mode": "enforce",
        "rules": chain["rules"],
    }
    stored = admin.post(base + "/guardrail-policies", json=body)
    assert stored.status_code == 201, stored.text


class FakeNer:
    model, revision = "acme/turkish-ner", "0123456789abcdef"

    async def find(self, text, categories):
        return []


def test_08t_26b_panel_reports_builtin_egress_pii(admin, base, monkeypatch):  # noqa: F811
    from ffcore.api import guardrails as api
    from ffcore.guardrails.settings import get_guardrail_settings

    # NER on: the built-in egress PII is then the NER variant (not DEFAULT_PII).
    monkeypatch.setenv("GUARDRAIL_EGRESS_NER", "true")
    get_guardrail_settings.cache_clear()
    monkeypatch.setattr(api, "local_ner", lambda: FakeNer())
    try:
        out = admin.post(
            base + "/guardrails/test",
            json={
                "text": "e-posta ayse@ornek.com",
                "stage": "input.pre",
                "policy_key": "default-egress",
                "action": "redact",
            },
        )
    finally:
        monkeypatch.undo()
        get_guardrail_settings.cache_clear()
    assert out.status_code == 200, out.text
    assert out.json()["builtin"] is True
