"""Reviewer probe for 08-tam-1a r1, run inside the review08t1a backend container.

docker exec -w /app -e PYTHONPATH=/app review08t1a-backend-1 python /tmp/probe08.py
Values are synthetic (example.test addresses); nothing secret is printed.
"""

import asyncio
import time
import uuid

from ffcore.core.config import get_settings
from ffcore.guardrails import masking, rules
from ffcore.runtime.events import redis_client


def redos() -> None:
    for word, n in (("token", 5000), ("token", 10000), ("password", 10000), ("token", 20000)):
        text = word + " " * n + "!"
        t0 = time.perf_counter()
        rules.find_secrets(text)
        print(f"REDOS {word}+{n} spaces: {time.perf_counter() - t0:.2f} s")
    text = ("token" + " " * 3000 + "x ") * 60  # 180k chars, under MAX_TEXT_CHARS
    t0 = time.perf_counter()
    rules.find_secrets(text)
    print(f"REDOS 180k mixed: {time.perf_counter() - t0:.2f} s")


def fp_fn() -> None:
    for t in (
        "token = getAccessToken() neden null?",
        "anahtar TeslimProjeleri kapsamında",
        "token: INC0012345678",
        "secret = loadSecretValue(x)",
        "Authorization: BearerTokenRequired",
        "API_KEY=Xk9QpLmZ2vRtWq",
        "Authorization: Bearer Xk9QpLmZ2vRtWq",
        "auth_token: QWERTYUIOPASDF",
        "DB_TOKEN=Xk9QpLmZ2vRt8",
    ):
        hits = [(f.category, f.value) for f in rules.find_secrets(t)]
        print(f"SECRETS {t!r} -> {hits}")


async def ttl_and_scope() -> None:
    redis = redis_client(get_settings())
    a, b = f"probe-a-{uuid.uuid4().hex[:8]}", f"probe-b-{uuid.uuid4().hex[:8]}"
    store = masking.RedisTokenStore(redis, ttl_s=2)
    t_old = await store.token_for(a, "EMAIL|ali@example.test", "ali@example.test")
    answer = f"Kayıt sahibi {t_old}."  # what the run stored before waiting
    print("TTL first token", t_old)
    await asyncio.sleep(3)  # TTL passes (an approval wait longer than PII_TOKEN_TTL_S)
    print("TTL after expiry", await masking.detokenize(answer, store=store, scope=a))
    t_new = await store.token_for(a, "EMAIL|veli@example.test", "veli@example.test")
    print("TTL new token after expiry", t_new)
    print("TTL old answer now reads", await masking.detokenize(answer, store=store, scope=a))
    # Conversation history: run A's placeholder text read in run B's scope.
    store = masking.RedisTokenStore(redis, ttl_s=60)
    ta = await store.token_for(a + "x", "EMAIL|ayse@example.test", "ayse@example.test")
    tb = await store.token_for(b, "EMAIL|fatma@example.test", "fatma@example.test")
    history = f"Önceki cevap: {ta}"
    print("SCOPE run A token", ta, "run B token", tb)
    print("SCOPE A's history in B", await masking.detokenize(history, store=store, scope=b))
    for k in (a, a + "x", b):
        await redis.delete("ffcore:pii:" + k)


if __name__ == "__main__":
    redos()
    fp_fn()
    asyncio.run(ttl_and_scope())
