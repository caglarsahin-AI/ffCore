"""08 tam 1c-b: the NER quality report and the pipeline's word-level aggregation.

The measurement of the two candidates (`python -m ffcore.guardrails.quality ... --ner`) scores
person, organization and location names the way the regex report scores identifiers (overlap
with an unmatched gold span of the same category). `aggregation_strategy="first"` labels whole
words: with "simple" a candidate split names into sub-word pieces (`Ay`, `şe`), so a name could
be masked in part (A-08T1C-0015, state/evidence/08t1c-b-explore2.log). The model is loaded
with int8 dynamic quantization (K-08T1C-0016 A): fp32 did not fit the latency budget.
"""

import sys
import types
from pathlib import Path

from ffcore.guardrails import quality
from ffcore.guardrails.findings import Finding
from ffcore.guardrails.recognizers import ner

REPO = Path(__file__).resolve().parents[3]

RECORDS = [
    {
        "text": "Ayşe Demir Ankara'da Acme A.Ş. için çalışır.",
        "entities": [
            {"start": 0, "end": 10, "category": "PERSON"},
            {"start": 11, "end": 17, "category": "LOCATION"},
            {"start": 21, "end": 30, "category": "ORGANIZATION"},
        ],
    },
    {"text": "Toplantı yarın.", "entities": []},
]


def fake_find(text, categories):
    out = []
    for value, category in (("Ayşe", "PERSON"), ("Acme", "ORGANIZATION"), ("yarın", "PERSON")):
        start = text.find(value)
        if start != -1 and category in categories:
            out.append(Finding(category, start, start + len(value), 0.9, "fake", value))
    return out


def test_08t1c_7_ner_quality_report_counts():
    report = quality.ner_quality_report(RECORDS, fake_find)
    assert list(report) == list(quality.NER_CATEGORIES)
    person, org, loc = (report[c] for c in quality.NER_CATEGORIES)
    # A partial span ("Ayşe" of "Ayşe Demir") counts as found; "yarın" is a false positive.
    assert (person.support, person.predicted, person.true_positive) == (1, 2, 1)
    assert (org.support, org.predicted, org.true_positive) == (1, 1, 1)
    assert (loc.support, loc.predicted, loc.true_positive) == (1, 0, 0)
    table = quality.markdown_table(report)
    assert "| `PERSON` | 1 | 2 | 1.00 | 0.50 |" in table


def test_08t1c_7b_regex_report_unchanged():
    # The regex report is the same function over the regex categories (docs table test 08_1b).
    report = quality.quality_report(RECORDS)
    assert set(report) == set(quality.REGEX_CATEGORIES)


def test_08t1c_7c_pipeline_aggregates_whole_words(monkeypatch):
    seen = {}

    def fake_pipeline(task, **kwargs):
        seen.update(kwargs, task=task)
        model = types.SimpleNamespace(config=types.SimpleNamespace(id2label={0: "O", 1: "B-PER"}))
        return types.SimpleNamespace(model=model)

    def fake_quantize(model, layers, dtype):
        seen["quantized"] = (model, layers, dtype)
        return model

    import torch

    monkeypatch.setitem(sys.modules, "transformers", types.SimpleNamespace(pipeline=fake_pipeline))
    monkeypatch.setattr("ffcore.knowledge.models.hf_path", lambda model, revision: "/m/x")
    monkeypatch.setattr(torch.ao.quantization, "quantize_dynamic", fake_quantize)
    ner.NerRecognizer.load("acme/ner", "0123456789abcdef")
    assert seen["task"] == "token-classification"
    assert seen["aggregation_strategy"] == "first"
    assert seen["stride"] == ner.STRIDE
    # K-08T1C-0016 A: int8 dynamic quantization of the linear layers, always (no setting).
    _, layers, dtype = seen["quantized"]
    assert layers == {torch.nn.Linear} and dtype == torch.qint8


def _env_example() -> dict[str, str]:
    path = REPO / ".env.example"
    pairs = (line.split("=", 1) for line in path.read_text(encoding="utf-8").splitlines())
    return {k: v for k, v in (p for p in pairs if len(p) == 2) if not k.startswith("#")}


def test_08t1c_7d_measured_winner_is_the_only_candidate():
    from ffcore.knowledge import models

    env = _env_example()
    model, revision = env["NER_MODEL"], env["NER_REVISION"]
    assert models.NER_CANDIDATES == (model,), "the loser leaves the list after the measurement"
    assert len(revision) == 40 and int(revision, 16) >= 0
    # `make models` downloads the measured commit, not `main` (a moved `main` would leave the
    # volume without the snapshot NER_REVISION names).
    assert models.NER_REVISIONS == {model: revision}
    # Weights as safetensors only: no pickle file is downloaded or listed (A-08T1C-0016).
    assert "pytorch_model.bin" not in models.NER_ALLOW_PATTERNS
    listed = (REPO / "deploy" / "offline" / "models.txt").read_text(encoding="utf-8")
    rows = [line.split() for line in listed.splitlines() if line.startswith("hf ")]
    files = {r[3] for r in rows if r[1] == model and r[2] == revision}
    assert {"config.json", "tokenizer.json", "vocab.txt", "model.safetensors"} <= files
    assert not any(r[1] == "savasy/bert-base-turkish-ner-cased" for r in rows)
    assert "pytorch_model.bin" not in files
