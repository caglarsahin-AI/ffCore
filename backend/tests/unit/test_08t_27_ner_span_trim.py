"""08 tam 1b r1 MINOR-5/6: a NER span is trimmed to the parts outside regex findings and existing
`<<PII_n>>` placeholders; it is never dropped whole, never nested around or inside a placeholder.

MINOR-5: `Ayşe Kaya05321234567` as one NER span lost the name because it overlapped the phone.
MINOR-6 (probe E6): a span covering `<<PII_1>>` stored the placeholder inside a new value; a span
inside one sent `<<<<PII_3>>>>` to the provider.
"""

import asyncio
import re

import pytest

from ffcore.guardrails import builtin, engine
from ffcore.guardrails.findings import Finding
from ffcore.guardrails.masking import PLACEHOLDER, MemoryTokenStore
from ffcore.knowledge import ingest_mask


class SpanNer:
    """Reports the given substring as one PERSON span (what a model might do)."""

    model, revision = "acme/turkish-ner", "0123456789abcdef"

    def __init__(self, span: str):
        self.span = span

    async def find(self, text, categories):
        start = text.find(self.span)
        if start == -1:
            return []
        end = start + len(self.span)
        return [Finding("PERSON", start, end, 0.95, "ner", text[start:end])]


def _egress(text, span):
    ctx = engine.EvalContext(
        run_id="r1", token_store=MemoryTokenStore(), egress_enabled=True, ner=SpanNer(span)
    )
    return asyncio.run(engine.evaluate(text, "egress", builtin.builtin_default(True), ctx=ctx))


def _well_formed(out: str) -> bool:
    return "<" not in PLACEHOLDER.sub("", out) and ">" not in PLACEHOLDER.sub("", out)


def test_08t_27_name_glued_to_a_phone_is_still_masked():
    out = _egress("Ayşe Kaya05321234567 aradı", "Ayşe Kaya05321234567").text_out
    for value in ("Ayşe", "Kaya", "05321234567"):
        assert value not in out
    assert out.endswith(" aradı") and _well_formed(out)
    assert len(PLACEHOLDER.findall(out)) == 2


def test_08t_27b_span_covering_a_placeholder_keeps_it_intact():
    text = "Bay <<PII_1>> Hanım aradı"
    out = _egress(text, "Bay <<PII_1>> Hanım").text_out
    # the carried placeholder stays its own token between the trimmed parts, never inside a value
    assert re.fullmatch(r"<<PII_\d+>> <<PII_1>> <<PII_\d+>> aradı", out), out
    assert _well_formed(out)


@pytest.mark.parametrize("span", ["PII_1", "<<PII_1>>", "<PII_1>"])
def test_08t_27c_span_inside_a_placeholder_is_dropped(span):
    text = "Bay <<PII_1>> aradı"
    out = _egress(text, span).text_out
    assert out == text


def test_08t_27d_pii_ner_filter_trims_too(monkeypatch):
    monkeypatch.setattr(ingest_mask, "ner_client", lambda: SpanNer("Ayşe Kaya05321234567"))
    masked, counts = asyncio.run(ingest_mask.PiiNerFilter().mask("Ayşe Kaya05321234567 aradı"))
    assert "Ayşe" not in masked and "05321234567" not in masked
    assert counts["PERSON"] == 1 and counts["TR_PHONE"] == 1
