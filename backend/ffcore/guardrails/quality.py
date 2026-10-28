"""Recognizer quality and latency measurement on the 13a PII set (data/samples/pii, C18).

Tools container: python -m ffcore.guardrails.quality ../data/samples/pii/pii-100.jsonl
prints the table that docs/guardrail.md carries (a test keeps the two equal).
"""

import json
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from ffcore.guardrails.categories import REGEX_CATEGORIES
from ffcore.guardrails.recognizers.regex import recognize


@dataclass(frozen=True)
class Row:
    support: int
    predicted: int
    true_positive: int

    @property
    def recall(self) -> float:
        return self.true_positive / self.support if self.support else 0.0

    @property
    def precision(self) -> float:
        return self.true_positive / self.predicted if self.predicted else 0.0


def load_set(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def quality_report(records: list[dict]) -> dict[str, Row]:
    """Per regex category: a prediction counts when it overlaps an unmatched gold span of the
    same category; every other prediction is a false positive."""
    counts = {code: [0, 0, 0] for code in REGEX_CATEGORIES}
    for record in records:
        gold = [e for e in record["entities"] if e["category"] in counts]
        for entity in gold:
            counts[entity["category"]][0] += 1
        matched: set[int] = set()
        for finding in recognize(record["text"]):
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
    return {code: Row(*values) for code, values in counts.items()}


def markdown_table(report: dict[str, Row]) -> str:
    lines = ["| Category | Support | Predicted | Recall | Precision |", "|---|---|---|---|---|"]
    for code, row in report.items():
        cells = (
            f"`{code}`",
            row.support,
            row.predicted,
            f"{row.recall:.2f}",
            f"{row.precision:.2f}",
        )
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


def latency_sample(chars: int = 1000, runs: int = 200) -> float:
    """P95 in milliseconds of `recognize` over a `chars`-long text."""
    text = latency_text(chars)
    recognize(text)  # compile and warm caches outside the measurement
    timings = []
    for _ in range(runs):
        started = time.perf_counter()
        recognize(text)
        timings.append((time.perf_counter() - started) * 1000)
    return statistics.quantiles(timings, n=100)[94]


if __name__ == "__main__":
    records = load_set(Path(sys.argv[1]))
    sys.stdout.write(markdown_table(quality_report(records)) + "\n")
    sys.stdout.write(f"\nregex P95, 1000 characters: {latency_sample():.2f} ms\n")
