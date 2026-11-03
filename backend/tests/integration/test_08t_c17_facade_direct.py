"""08-tam-1a, C17 on the facade's direct model path, through the real LiteLLM and the fake
provider: the e-mail address in the tool result leaves as a placeholder (egress), the fake model
answers "hello " + the tool result it saw (so its answer carries the placeholder), and the caller
gets the value back, live stream and one piece alike. With an enforced `pii` rule on the output
the placeholder stays (the policy hides personal data from answers)."""

import json

import pytest

from tests.integration import test_06b_direct as base
from tests.integration.facade_support import *  # noqa: F403 - fixtures
from tests.integration.litellm_support import fake_requests
from tests.integration.test_06b_direct import EMAIL, TOOL, _policy, _tool_turn

# The 06b fixtures (a project with `chat-default` and `tooly`, a console, a chat_direct key).
facade_settings = base.facade_settings
direct = base.direct

pytestmark = pytest.mark.usefixtures("clean_litellm")


def _sent_to_provider():
    return json.dumps(fake_requests()[-1], ensure_ascii=False)


def test_08t_7c_direct_answer_reversed_for_the_caller(direct):
    _, _, _, client = direct
    response = client.chat("tooly", messages=_tool_turn(f"kayit {EMAIL}"), tools=[TOOL])
    assert response.status_code == 200, response.text
    assert EMAIL not in _sent_to_provider()  # egress: the provider saw a placeholder
    content = response.json()["choices"][0]["message"]["content"]
    assert content == f"hello kayit {EMAIL}"
    assert "<<PII_" not in response.text


def test_08t_8_direct_live_stream_reversed(direct):
    _, _, _, client = direct
    status, chunks, lines = client.stream(
        "tooly", messages=_tool_turn(f"kayit {EMAIL}"), tools=[TOOL]
    )
    assert status == 200
    assert EMAIL not in _sent_to_provider()
    text = "".join(ch["delta"].get("content") or "" for c in chunks for ch in c["choices"])
    assert text == f"hello kayit {EMAIL}"
    assert "<<PII_" not in "\n".join(lines)
    assert lines[-1] == "data: [DONE]"


def test_08t_9_enforced_output_pii_keeps_the_placeholder(direct):
    project, console, _, client = direct
    _policy(
        console,
        project,
        [
            {
                "type": "pii",
                "action": "tokenize",
                "stages": ["egress"],
                "pii_policy_key": "default",
            },
            {"type": "pii", "stages": ["output.pre"], "pii_policy_key": "default"},
        ],
    )
    response = client.chat("tooly", messages=_tool_turn(f"kayit {EMAIL}"), tools=[TOOL])
    assert response.status_code == 200, response.text
    content = response.json()["choices"][0]["message"]["content"]
    assert EMAIL not in content and content.startswith("hello kayit <<PII_")
