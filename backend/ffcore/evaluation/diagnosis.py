"""Stage diagnosis of an exam item (brief 09, PayCore correction D7).

`outcome` (C24) is the exam's own vocabulary, separate from `runs.outcome_label`. The first
stage the item falls at wins. Order follows the search code (DRIFT-164, K-09-0007 S5): the
rerank floor is applied before the `top_k` cut (knowledge/search.py), so

  not_retrieved       an expected document has no candidate (hybrid top-N, kb_queries)
  below_rerank_floor  every candidate of an expected document is under the floor
  not_reranked        above the floor but not among the selected sources (top_k cut)
  declined / below_threshold / answered   the run's own label (06a finalize)
  unanswerable_held / unanswerable_answered   answerable=false items

A stage passes only if every expected document passes it. Items without expected documents
(SQL) skip the retrieval stages. A run that did not complete has no outcome (None); the engine
counts it by status instead.
"""

from dataclasses import dataclass, field
from pathlib import PurePosixPath

from ffcore.evaluation.scorers import normalize

OUTCOMES = (
    "not_retrieved",
    "not_reranked",
    "below_rerank_floor",
    "declined",
    "below_threshold",
    "answered",
    "unanswerable_held",
    "unanswerable_answered",
)


@dataclass(frozen=True)
class Candidate:
    document: str  # file name (or stem) of the candidate's document
    below_floor: bool  # under the rerank floor (or the min score when the reranker is off)


@dataclass(frozen=True)
class RunFacts:
    status: str
    outcome_label: str | None
    answerable: bool
    expected_docs: list[str] = field(default_factory=list)
    candidates: list[Candidate] = field(default_factory=list)
    selected: list[str] = field(default_factory=list)


def _stem(name: str) -> str:
    return normalize(PurePosixPath(str(name).replace("\\", "/")).stem)


def diagnose(f: RunFacts) -> str | None:
    if f.status != "completed" or f.outcome_label is None:
        return None
    if not f.answerable:
        return "unanswerable_answered" if f.outcome_label == "answered" else "unanswerable_held"
    expected = {_stem(d) for d in f.expected_docs}
    if expected:
        by_doc: dict[str, list[Candidate]] = {}
        for c in f.candidates:
            by_doc.setdefault(_stem(c.document), []).append(c)
        if any(d not in by_doc for d in expected):
            return "not_retrieved"
        if any(all(c.below_floor for c in by_doc[d]) for d in expected):
            return "below_rerank_floor"
        selected = {_stem(s) for s in f.selected}
        if any(d not in selected for d in expected):
            return "not_reranked"
    if f.outcome_label in ("declined", "below_threshold", "answered"):
        return f.outcome_label
    raise ValueError(f"unknown outcome_label {f.outcome_label!r}")
