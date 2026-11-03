"""08-tam-1a r5 MAJOR-r5-1 (KARARLAR "C17 HTML kuralı, düzeltmeler" (g)): the scan's 32-character
tail can cut a placeholder between its two `<`; the HTML exception must not depend on the
character before it, or the rest of the stream took `<PII_1>>` for a tag and the owner saw
placeholders (the reviewer's probe, state/reviews/08-tam-1a-r5-tail-probe.py: 97/200 answers lost
a value). An element like `<PII_1 style…` is still a tag."""

import asyncio
import random
import re

import pytest

from ffcore.guardrails.masking import ContextReveal, MemoryTokenStore, StreamDetokenizer

run = asyncio.run
VALUE = "ali@example.test"
PH = re.compile(r"(<<PII_\d+>>)")
TEXT = (
    "Kişi {t} kayıtlı. Bu cümle otuz iki karakterden uzun bir devam metnidir ve sürer.\n"
    "İkinci satırda yine {t} geçiyor ve ardından biraz daha düz metin var.\n"
    "Son satır: {t}."
)


def _live_pieces(text, size):
    # live entries keep whole placeholders (the writer's aligner)
    out = []
    for part in PH.split(text):
        if PH.fullmatch(part):
            out.append(part)
        else:
            out += [part[i : i + size] for i in range(0, len(part), size)]
    return [p for p in out if p]


async def _setup():
    store = MemoryTokenStore()
    token = await store.token_for("s", "EMAIL_ADDRESS:" + VALUE, VALUE)
    return store, TEXT.format(t=token)


@pytest.mark.parametrize("size", [1, 2, 3, 4, 5, 6, 8, 11])
def test_08t_r5_facade_stream_shows_every_value(size):
    async def go():
        store, text = await _setup()
        det = StreamDetokenizer(store, "s")
        out = [await det.feed(text[i : i + size]) for i in range(0, len(text), size)]
        return "".join(out) + await det.flush()

    assert run(go()).count(VALUE) == 3


@pytest.mark.parametrize("size", [1, 2, 3, 4, 5, 6, 8, 11])
def test_08t_r5_console_live_shows_every_value(size):
    async def go():
        store, text = await _setup()
        cr = ContextReveal(store, "s")
        pieces = _live_pieces(text, size)
        return "".join([(await cr.data({"text": p}, stream_text=True))["text"] for p in pieces])

    assert run(go()).count(VALUE) == 3


def test_08t_r5_random_token_pieces_lose_no_value():
    async def go():
        store, text = await _setup()
        rng, lost = random.Random(5), 0
        for _ in range(200):
            cr = ContextReveal(store, "s")
            pieces, rest = [], text
            while rest:
                whole = PH.match(rest)
                nxt = PH.search(rest)
                limit = nxt.start() if nxt and nxt.start() else len(rest)
                n = len(whole.group(0)) if whole else min(rng.randint(1, 6), limit)
                pieces.append(rest[:n])
                rest = rest[n:]
            live = "".join([(await cr.data({"text": p}, stream_text=True))["text"] for p in pieces])
            lost += live.count(VALUE) < 3
        return lost

    assert run(go()) == 0
