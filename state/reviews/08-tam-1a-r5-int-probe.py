"""Reviewer integration probe for 08-tam-1a r5 (60f2250), mounted into the tools container as
backend/tests/integration/test_zz_review_08t1a_r5.py for the run and removed afterwards.

Direct facade path, real LiteLLM and fake provider:
(1) KARARLAR f′ / r4 MINOR-r4-1: a policy whose egress `pii` rule says `on_error: allow` (a policy field); the tool
    result carries <<PII_99999997>> and two e-mail addresses, so the second value is past the
    range. Expected: a coded failure (placeholder_out_of_range) and no raw address at the provider.
(2) f′: a text carrying <<PII_99999999>> keeps working (the number is ignored; the value gets
    <<PII_1>> and comes back).
"""

import json

import pytest

from tests.integration import test_06b_direct as direct_base
from tests.integration.facade_support import *  # noqa: F403 - fixtures
from tests.integration.litellm_support import fake_requests
from tests.integration.test_06b_direct import TOOL, _tool_turn

facade_settings = direct_base.facade_settings
direct = direct_base.direct
A, B = "birinci.kisi@example.test", "ikinci.kisi@example.test"


def _egress_on():
    from ffcore.guardrails.settings import get_guardrail_settings

    return get_guardrail_settings().guardrail_egress_enabled


@pytest.mark.usefixtures("clean_litellm")
def test_zz_r5_range_under_on_error_log(direct):
    project, console, _, client = direct
    # `on_error` is a policy field (block | allow): `allow` lets a failed rule pass the text on
    response = console.post(
        f"/api/v1/projects/{project}/guardrail-policies",
        json={
            "key": "default",
            "name": "Facade",
            "mode": "enforce",
            "on_error": "allow",
            "rules": [
                {"type": "pii", "action": "tokenize", "stages": ["egress"], "pii_policy_key": "default"}
            ],
        },
    )
    assert response.status_code == 201, response.text
    before = len(fake_requests())
    response = client.chat(
        "tooly", messages=_tool_turn(f"<<PII_99999997>> {A} {B}"), tools=[TOOL]
    )
    sent = json.dumps(fake_requests()[before:], ensure_ascii=False)
    print(
        f"PROBE on_error=allow range: status {response.status_code}, "
        f"body {response.text[:160]!r}, provider requests {len(fake_requests()) - before}, "
        f"raw A at provider {A in sent}, raw B at provider {B in sent}"
    )
    if _egress_on():
        assert response.status_code >= 400
        assert "placeholder_out_of_range" in response.text
        assert A not in sent and B not in sent


@pytest.mark.usefixtures("clean_litellm")
def test_zz_r5_carried_99999999_keeps_working(direct):
    _, _, _, client = direct
    before = len(fake_requests())
    response = client.chat("tooly", messages=_tool_turn(f"<<PII_99999999>> {A}"), tools=[TOOL])
    sent = json.dumps(fake_requests()[before:], ensure_ascii=False)
    content = response.json()["choices"][0]["message"]["content"] if response.status_code == 200 else ""
    print(
        f"PROBE carried 99999999: status {response.status_code}, provider saw "
        f"{'<<PII_1>>' if '<<PII_1>>' in sent else 'other'}, raw A at provider {A in sent}, answer {content!r}"
    )
    assert response.status_code == 200
    if _egress_on():
        assert A not in sent and "<<PII_1>>" in sent
