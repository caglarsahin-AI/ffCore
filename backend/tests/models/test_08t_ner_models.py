"""08 tam 1c-b with the real NER weights: the model `.env.example` names (the measured winner).

Acceptance 1 of 08 full 1b (person-name recall), the docs table equal to the measurement,
whole-word spans, the pipeline's windows over 512 tokens (r1 NOTE-3) and the egress PERSON
tokenize of the built-in policy with GUARDRAIL_EGRESS_NER=true.
Run: `make test-models` (RUN_MODEL_TESTS=1), weights from `make models`, no network needed.
Acceptance 3 (latency) depends on the machine: test_08t_ner_latency.py, `make test-ner-latency`.
"""

import asyncio
import re
from pathlib import Path

import pytest

from ffcore.guardrails import builtin, engine, quality
from ffcore.guardrails.masking import MemoryTokenStore
from ffcore.guardrails.recognizers.ner import LocalNer

pytestmark = pytest.mark.models

REPO = Path(__file__).resolve().parents[3]
PII_SET = REPO / "data" / "samples" / "pii" / "pii-100.jsonl"
DOCS = REPO / "docs" / "guardrail.md"
NAMES = ("Ayşe Demir", "Mehmet Yılmaz", "Zeynep Kaya", "Ali Çelik", "Elif Şahin")


def _winner() -> tuple[str, str]:
    env = {}
    for line in (REPO / ".env.example").read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep and not key.startswith("#"):
            env[key] = value
    return env["NER_MODEL"], env["NER_REVISION"]


@pytest.fixture(scope="module")
def client() -> LocalNer:
    model, revision = _winner()
    local = LocalNer(model, revision)
    local.load()
    return local


@pytest.fixture(scope="module")
def report(client):
    return quality.ner_quality_report(quality.load_set(PII_SET), client._recognize)


def test_08t_1_ner_recall_person(report):
    assert report["PERSON"].recall >= 0.85, report["PERSON"]


def test_08t1c_13_person_names_fully_covered(report):
    """r1 MINOR-2: recall counts any overlap; every letter of a gold name must be inside the
    model's PERSON spans (above the engine threshold) for the name to count as covered."""
    assert report["PERSON"].coverage >= 0.85, report["PERSON"]


def test_08t_1b_ner_quality_report_matches_docs(report):
    assert quality.markdown_table(report) in DOCS.read_text(encoding="utf-8")


def test_08t1c_8_person_spans_are_whole_words(client):
    for record in quality.load_set(PII_SET):
        text = record["text"]
        for f in client._recognize(text, {"PERSON"}):
            before = text[f.start - 1] if f.start else " "
            after = text[f.end] if f.end < len(text) else " "
            assert not before.isalnum() and not after.isalnum(), (record["id"], f.value)


def test_08t1c_9_long_text_windows_find_every_name(client):
    """r1 NOTE-3: a text far over 512 tokens; the pipeline's overlapping windows (STRIDE) cover
    every letter of every name, with offsets into the whole text, including names on a window
    edge, and nothing outside the names. The model may tag a surname as its own `B-PER`
    (`Mehmet` + `Yılmaz`, short texts too): two adjacent spans, both masked."""
    filler = "Sözleşmenin ek protokolüne göre teslimat süresi otuz iş günüdür. "
    parts, expected = [], []
    for i in range(60):
        name = NAMES[i % len(NAMES)]
        offset = sum(len(p) for p in parts)
        parts.append(f"{name} toplantıya katıldı. ")
        expected.append((offset, offset + len(name)))
        parts.append(filler * (1 + i % 3))
    text = "".join(parts)
    tokens = len(client.load()._pipeline.tokenizer(text)["input_ids"])
    assert tokens > 3 * 512, tokens
    found = sorted((f.start, f.end) for f in client._recognize(text, {"PERSON"}))
    for start, end in expected:
        letters = [i for i in range(start, end) if not text[i].isspace()]
        uncovered = [i for i in letters if not any(s <= i < e for s, e in found)]
        assert not uncovered, text[start:end]
    outside = [(s, e) for s, e in found if not any(a <= s and e <= b for a, b in expected)]
    assert not outside, [text[s:e] for s, e in outside]
    assert len(found) == len(set(found))  # the window overlap repeats no span


def test_08t1c_10_egress_person_tokenized_with_the_real_model(client):
    """The property, not the model's span split (K-08T1C-0021): no raw name or phone leaves;
    the name is one or two placeholders (the model may tag the surname on its own), the phone
    one, the rest of the text unchanged."""
    pol = builtin.builtin_default(True)
    ctx = engine.EvalContext(
        run_id="r1", token_store=MemoryTokenStore(), egress_enabled=True, ner=client
    )
    decision = asyncio.run(
        engine.evaluate("Ayşe Demir 0532 123 45 67 arar.", "egress", pol, ctx=ctx)
    )
    out = decision.text_out
    for raw in ("Ayşe", "Demir", "0532", "123 45 67"):
        assert raw not in out, out
    assert re.fullmatch(r"(<<PII_[0-9]+>> ){2,3}arar\.", out), out


def test_08t1c_11_int8_quality_equals_fp32(client, report):
    """K-08T1C-0016 A: the int8 model the API loads finds the same person and organization
    names as the fp32 weights on the PII set (location within one prediction)."""
    from transformers import pipeline

    from ffcore.guardrails.recognizers.ner import STRIDE, NerRecognizer
    from ffcore.knowledge.models import hf_path

    model, revision = _winner()
    path = str(hf_path(model, revision))
    pipe = pipeline(
        "token-classification",
        model=path,
        tokenizer=path,
        aggregation_strategy="first",
        stride=STRIDE,
        device=-1,
    )
    fp32 = NerRecognizer(model, revision, pipeline=pipe, labels=pipe.model.config.id2label)
    reference = quality.ner_quality_report(quality.load_set(PII_SET), fp32.recognize)
    assert report["PERSON"] == reference["PERSON"]  # covered included
    assert report["ORGANIZATION"] == reference["ORGANIZATION"]
    assert report["LOCATION"].recall == reference["LOCATION"].recall
    assert abs(report["LOCATION"].predicted - reference["LOCATION"].predicted) <= 1
