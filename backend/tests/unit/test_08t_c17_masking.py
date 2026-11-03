"""08-tam-1a, C17 (plan/08 acceptance, FOLLOWUP-141): placeholders go back to their values at the
exit, and a placeholder split across two stream chunks never reaches a client raw.

- `PlaceholderAligner`: the writer side. A model delta that ends inside a placeholder holds that
  tail (at most 15 characters) until the next delta or the end, so every published `token`
  entry carries whole placeholders only and a reader can turn them back entry by entry.
- `StreamDetokenizer`: aligner + reversal in one, for a stream read and written by one request
  (the facade's direct model path).
- `detokenize_json`: every string of an event's data, within one scope; unknown placeholders
  stay as they are and are counted.
"""

import asyncio
import random

import pytest

from ffcore.guardrails.findings import Finding
from ffcore.guardrails.masking import (
    PLACEHOLDER,
    MemoryTokenStore,
    PlaceholderAligner,
    StreamDetokenizer,
    apply_action,
    detokenize_json,
)

run = asyncio.run


def _split_everywhere(text):
    for i in range(len(text) + 1):
        yield [text[:i], text[i:]]


def _aligned(pieces):
    aligner = PlaceholderAligner()
    out = [aligner.feed(p) for p in pieces]
    out.append(aligner.flush())
    return out


def _whole_in_one_piece(text, out):
    """Every placeholder of `text` lies inside one published piece (none is split)."""
    bounds, at = [], 0
    for piece in out:
        bounds.append((at, at + len(piece)))
        at += len(piece)
    for match in PLACEHOLDER.finditer(text):
        assert any(a <= match.start() and match.end() <= b for a, b in bounds), (match, out)


def test_08t_8_aligner_never_publishes_a_partial_placeholder():
    text = "Ad <<PII_1>> ve <<PII_12>> geldi, <<PII_3>>"
    for pieces in _split_everywhere(text):
        out = _aligned(pieces)
        assert "".join(out) == text
        _whole_in_one_piece(text, out)


def test_08t_8_aligner_random_chunks():
    rng = random.Random(17)
    parts = ["x", " ", "<", ">", "<<PII_7>>", "<<PII_42>>", "PII_"]
    text = "".join(rng.choice(parts) for _ in range(400))
    for _ in range(300):
        cuts = sorted(rng.sample(range(len(text)), rng.randint(1, 30)))
        pieces = [text[a:b] for a, b in zip([0, *cuts], [*cuts, len(text)], strict=True)]
        out = _aligned(pieces)
        assert "".join(out) == text
        _whole_in_one_piece(text, out)


def test_08t_8b_text_that_is_not_a_placeholder_is_not_held():
    aligner = PlaceholderAligner()
    assert aligner.feed("a < b and <<x") == "a < b and <<x"
    # more than the longest placeholder (16 characters): not a placeholder, passes as it is
    assert aligner.feed("<<PII_123456789") == "<<PII_123456789"
    assert aligner.feed("<<PII_1") == ""
    assert aligner.flush() == "<<PII_1"  # end of stream: the tail as it is, never dropped


def _store_with(values):
    store = MemoryTokenStore()

    async def fill():
        text = " ".join(values)
        findings, at = [], 0
        for v in values:
            start = text.index(v, at)
            findings.append(Finding("PERSON", start, start + len(v), 1.0, "test", v))
            at = start + len(v)
        return await apply_action(text, findings, "tokenize", store=store, scope="run-1")

    tokenized = run(fill())
    return store, tokenized


def test_08t_8_stream_split_placeholder_reversed():
    store, tokenized = _store_with(["Ayşe Kaya", "Mehmet Demir"])
    assert tokenized == "<<PII_1>> <<PII_2>>"
    for pieces in _split_everywhere("Merhaba <<PII_1>>, <<PII_2>> aradı."):

        async def stream(pieces=pieces):
            sd = StreamDetokenizer(store, "run-1")
            out = [await sd.feed(p) for p in pieces]
            out.append(await sd.flush())
            return out

        out = run(stream())
        assert "".join(out) == "Merhaba Ayşe Kaya, Mehmet Demir aradı."
        assert not any("<<PII_" in piece for piece in out), (pieces, out)


def test_08t_9_other_scope_placeholder_not_reversed():
    store, _ = _store_with(["Ayşe Kaya"])

    async def go():
        sd = StreamDetokenizer(store, "run-2")
        return await sd.feed("<<PII_1>> merhaba") + await sd.flush(), sd.unresolved

    text, unresolved = run(go())
    assert text == "<<PII_1>> merhaba"
    assert unresolved == 1


def test_08t_7_detokenize_json_walks_every_string():
    store, _ = _store_with(["Ayşe Kaya", "05321234567"])
    data = {
        "text": "<<PII_1>> aradı",
        "arguments": {"to": "<<PII_2>>", "list": ["<<PII_1>>", 3, None]},
        "n": 1,
        "unknown": "<<PII_99>>",
    }
    out, unresolved = run(detokenize_json(data, store=store, scope="run-1"))
    assert out == {
        "text": "Ayşe Kaya aradı",
        "arguments": {"to": "05321234567", "list": ["Ayşe Kaya", 3, None]},
        "n": 1,
        "unknown": "<<PII_99>>",
    }
    assert unresolved == 1
    assert data["text"] == "<<PII_1>> aradı"  # the input is not changed in place


@pytest.mark.parametrize("value", ["", "no placeholder here", 7, None])
def test_08t_7_detokenize_json_without_placeholders_is_identity(value):
    store = MemoryTokenStore()
    assert run(detokenize_json(value, store=store, scope="s")) == (value, 0)


def test_08t_9_count_placeholders_without_lookup():
    from ffcore.guardrails.masking import count_placeholders

    data = {"text": "<<PII_1>> ve <<PII_2>>", "args": ["<<PII_3>>", 4], "n": "<<PII_"}
    assert count_placeholders(data) == 3
