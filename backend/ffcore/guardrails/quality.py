"""Recognizer quality and latency measurement on the 13a PII set (data/samples/pii, C18).

Tools container: python -m ffcore.guardrails.quality ../data/samples/pii/pii-100.jsonl
prints the table that docs/guardrail.md carries (a test keeps the two equal).

With `--ner MODEL@REVISION` (repeatable; weights from `make models`, offline) it also prints the
person, organization and location table of each NER model and its P95 for 1,000 characters
(local rules and NER together), the 08 full 1c measurement of the candidates.
"""

import argparse
import json
import statistics
import sys
import time
from collections.abc import Callable, Collection
from dataclasses import dataclass
from pathlib import Path

from ffcore.guardrails.builtin import builtin_egress_pii
from ffcore.guardrails.categories import REGEX_CATEGORIES
from ffcore.guardrails.findings import Finding
from ffcore.guardrails.recognizers.regex import recognize

NER_CATEGORIES = ("PERSON", "ORGANIZATION", "LOCATION")

FindFn = Callable[[str, Collection[str]], list[Finding]]


@dataclass(frozen=True)
class Row:
    support: int
    predicted: int
    true_positive: int
    # NER only (r1 MINOR-2): gold spans whose every letter is inside predicted spans of the same
    # category; `true_positive` counts any overlap ("Ayşe" of "Ayşe Demir").
    covered: int | None = None

    @property
    def recall(self) -> float:
        return self.true_positive / self.support if self.support else 0.0

    @property
    def precision(self) -> float:
        return self.true_positive / self.predicted if self.predicted else 0.0

    @property
    def coverage(self) -> float:
        return (self.covered or 0) / self.support if self.support else 0.0


def load_set(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _score(
    records: list[dict],
    categories: Collection[str],
    find: FindFn,
    *,
    min_confidence: float = 0.0,
    with_coverage: bool = False,
) -> dict[str, Row]:
    """Per category: a prediction counts when it overlaps an unmatched gold span of the same
    category; every other prediction is a false positive. Predictions under `min_confidence`
    are dropped first, as the engine drops them."""
    counts = {code: [0, 0, 0, 0] for code in categories}
    for record in records:
        text = record["text"]
        gold = [e for e in record["entities"] if e["category"] in counts]
        for entity in gold:
            counts[entity["category"]][0] += 1
        found = [f for f in find(text, categories) if f.score >= min_confidence]
        matched: set[int] = set()
        for finding in found:
            counts[finding.category][1] += 1
            for i, entity in enumerate(gold):
                if (
                    i not in matched
                    and entity["category"] == finding.category
                    and finding.start < entity["end"]
                    and entity["start"] < finding.end
                ):
                    matched.add(i)
                    counts[finding.category][2] += 1
                    break
        for entity in gold:
            spans = [(f.start, f.end) for f in found if f.category == entity["category"]]
            letters = [i for i in range(entity["start"], entity["end"]) if text[i].isalnum()]
            if all(any(s <= i < e for s, e in spans) for i in letters):
                counts[entity["category"]][3] += 1
    return {
        code: Row(s, p, t, covered if with_coverage else None)
        for code, (s, p, t, covered) in counts.items()
    }


def quality_report(records: list[dict]) -> dict[str, Row]:
    """The regex recognizers over the regex categories."""
    return _score(records, REGEX_CATEGORIES, lambda text, categories: recognize(text))


# The built-in egress policy's threshold: the engine drops NER findings below it (r1 MINOR-3).
NER_MIN_CONFIDENCE = builtin_egress_pii(True).min_confidence


def ner_quality_report(records: list[dict], find: FindFn) -> dict[str, Row]:
    """A NER model (`find(text, categories)`) over person, organization and location, with the
    engine's threshold and the full-coverage count."""
    return _score(
        records, NER_CATEGORIES, find, min_confidence=NER_MIN_CONFIDENCE, with_coverage=True
    )


def markdown_table(report: dict[str, Row]) -> str:
    coverage = any(row.covered is not None for row in report.values())
    header = "| Category | Support | Predicted | Recall | Precision |"
    rule = "|---|---|---|---|---|"
    if coverage:
        header, rule = header + " Covered |", rule + "---|"
    lines = [header, rule]
    for code, row in report.items():
        cells = [
            f"`{code}`",
            row.support,
            row.predicted,
            f"{row.recall:.2f}",
            f"{row.precision:.2f}",
        ]
        if coverage:
            cells.append(f"{row.coverage:.2f}")
        lines.append("| " + " | ".join(str(c) for c in cells) + " |")
    return "\n".join(lines)


_FILLER = (
    "Sözleşmenin ek protokolüne göre teslimat süresi otuz iş günüdür ve gecikmede ceza uygulanır. "
)
_VALUES = (
    "TC kimlik 10000000146, ",
    "tel 0532 256 60 38, ",
    "IBAN TR60 9987 5070 0891 8096 0391 33, ",
    "e-posta ayse@ornek.com, ",
    "kart 4111 1111 1111 1111. ",
)


def latency_text(chars: int) -> str:
    """Deterministic text of exactly `chars` characters with all five regex categories."""
    parts, i = [], 0
    while sum(len(p) for p in parts) < chars:
        parts.append(_FILLER if i % 2 == 0 else _VALUES[(i // 2) % len(_VALUES)])
        i += 1
    return "".join(parts)[:chars]


def _p95(call: Callable[[], object], runs: int) -> float:
    call()  # compile and warm caches outside the measurement
    timings = []
    for _ in range(runs):
        started = time.perf_counter()
        call()
        timings.append((time.perf_counter() - started) * 1000)
    return statistics.quantiles(timings, n=100)[94]


def latency_sample(chars: int = 1000, runs: int = 200) -> float:
    """P95 in milliseconds of `recognize` over a `chars`-long text."""
    text = latency_text(chars)
    return _p95(lambda: recognize(text), runs)


def ner_latency_sample(find: FindFn, chars: int = 1000, runs: int = 100) -> float:
    """P95 in milliseconds of the local rules and the NER together over a `chars`-long text."""
    text = latency_text(chars)

    def both():
        recognize(text)
        find(text, NER_CATEGORIES)

    return _p95(both, runs)


def _ner_rows(records: list[dict], spec: str) -> str:
    import torch

    from ffcore.guardrails.recognizers.ner import LocalNer

    model, _, revision = spec.partition("@")
    client = LocalNer(model, revision)
    client.load()
    report = ner_quality_report(records, client._recognize)
    p95 = ner_latency_sample(client._recognize)
    return (
        f"\n{model}@{revision} (torch threads {torch.get_num_threads()})\n"
        f"{markdown_table(report)}\n"
        f"P95, 1000 characters, local rules + NER: {p95:.0f} ms\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("set", type=Path)
    parser.add_argument("--ner", action="append", default=[], metavar="MODEL@REVISION")
    args = parser.parse_args()
    records = load_set(args.set)
    sys.stdout.write(markdown_table(quality_report(records)) + "\n")
    sys.stdout.write(f"\nregex P95, 1000 characters: {latency_sample():.2f} ms\n")
    for spec in args.ner:
        sys.stdout.write(_ner_rows(records, spec))
