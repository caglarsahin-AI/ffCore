"""Reviewer probe for 08-tam-1a r5 (60f2250): does the 32-character tail window take a whole
placeholder for an HTML tag (`<PII_1>>` once its first `<` falls out of the window)? Live entries
keep whole placeholders (the writer's aligner); the facade direct stream gets raw provider deltas.

docker exec -w /app -e PYTHONPATH=/app review08t1a-backend-1 python /tmp/probe08r5tail.py
"""

import asyncio
import random
import re

from ffcore.guardrails import masking

VALUE = "ali@example.test"
PH = re.compile(r"(<<PII_\d+>>)")


def live_pieces(text, size):
    out = []
    for part in PH.split(text):
        if PH.fullmatch(part):
            out.append(part)
        else:
            out += [part[i : i + size] for i in range(0, len(part), size)]
    return [p for p in out if p]


async def main():
    store = masking.MemoryTokenStore()
    t = await store.token_for("s", "EMAIL_ADDRESS:" + VALUE, VALUE)
    text = (
        f"Kişi {t} kayıtlı. Bu cümle otuz iki karakterden uzun bir devam metnidir ve sürer.\n"
        f"İkinci satırda yine {t} geçiyor ve ardından biraz daha düz metin var.\n"
        f"Son satır: {t}."
    )
    for size in (1, 2, 3, 4, 5, 6, 8, 11):
        det = masking.StreamDetokenizer(store, "s")
        out = ""
        for i in range(0, len(text), size):
            out += await det.feed(text[i : i + size])
        out += await det.flush()
        cr = masking.ContextReveal(store, "s")
        live = ""
        for p in live_pieces(text, size):
            live += (await cr.data({"text": p}, stream_text=True))["text"]
        one, _, _ = await masking.reveal_text(text, store=store, scope="s")
        print(
            f"TAIL {size}-char: one piece {one.count(VALUE)}/3, "
            f"facade stream {out.count(VALUE)}/3, console live {live.count(VALUE)}/3"
        )
    # random token-like chunking (1-6 chars), 200 trials, live entries
    rng = random.Random(5)
    lost = 0
    for _ in range(200):
        cr = masking.ContextReveal(store, "s")
        pieces, rest = [], text
        while rest:
            m = PH.match(rest)
            n = len(m.group(0)) if m else min(rng.randint(1, 6), (PH.search(rest).start() if PH.search(rest) else len(rest)) or 1)
            pieces.append(rest[:n])
            rest = rest[n:]
        live = "".join([(await cr.data({"text": p}, stream_text=True))["text"] for p in pieces])
        lost += live.count(VALUE) < 3
    print(f"TAIL random 1-6 char live entries: {lost}/200 answers lost at least one value")


asyncio.run(main())
