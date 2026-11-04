"""Exam scorers (09): pure functions over what a run produced.

Each scorer returns a `Score`: `value` in [0, 1], `passed`, a short `comment` code and a
`status` (`ok`, `not_run` when the item gives the scorer nothing to check, `error`). A scorer
never invents a value: no expectation means `not_run`, unreadable judge output raises
`JudgeParseError` and the engine records the item as a judge error (fail-loud, ARCH-06).

`llm_judge` itself (model call, rubric prompt, egress) lives in `evaluation/judge.py`; here
only its output parsing. `semantic` takes vectors; the engine gets them from the API process's
`/internal/embed` (the worker loads no model, C10).
"""

import json
import math
import re
import unicodedata
from dataclasses import dataclass
from pathlib import PurePosixPath

from jsonschema import Draft202012Validator

SCORERS = (
    "contains",
    "regex",
    "json_schema",
    "cites_source",
    "semantic",
    "llm_judge",
    "sql_result",
    "latency_cost",
)
JUDGE_MIN, JUDGE_MAX = 1, 5


@dataclass(frozen=True)
class Score:
    name: str
    value: float | None
    passed: bool | None
    comment: str = ""
    status: str = "ok"


def _not_run(name: str, why: str) -> Score:
    return Score(name, None, None, why, "not_run")


def normalize(text: str) -> str:
    """NFKC, case-folded, whitespace collapsed. Case folding turns Turkish "İ" into "i" plus a
    combining dot; the dot is dropped so "İzmir" and "izmir" compare equal."""
    folded = unicodedata.normalize("NFKC", text).casefold().replace("̇", "")
    return " ".join(folded.split())


def contains(answer: str, expected: list[str]) -> Score:
    if not expected:
        return _not_run("contains", "no_expectation")
    text = normalize(answer)
    found = sum(1 for e in expected if normalize(e) in text)
    value = found / len(expected)
    return Score("contains", value, found == len(expected), f"{found}/{len(expected)}")


def regex(answer: str, pattern: str | None) -> Score:
    if not pattern:
        return _not_run("regex", "no_expectation")
    ok = re.search(pattern, answer) is not None
    return Score("regex", 1.0 if ok else 0.0, ok)


def json_schema(answer: str, schema: dict | None) -> Score:
    if not schema:
        return _not_run("json_schema", "no_expectation")
    try:
        document = json.loads(answer)
    except ValueError:
        return Score("json_schema", 0.0, False, "invalid_json")
    errors = list(Draft202012Validator(schema).iter_errors(document))
    if errors:
        return Score("json_schema", 0.0, False, f"schema_errors={len(errors)}")
    return Score("json_schema", 1.0, True)


def _stem(name: str) -> str:
    return normalize(PurePosixPath(str(name).replace("\\", "/")).stem)


def cites_source(selected: list[str], must_cite: list[str]) -> Score:
    """Every expected document is among the run's sources, matched by file stem (the seed may
    upload a DOCX as <stem>.txt; same rule as 13b `make eval`)."""
    if not must_cite:
        return _not_run("cites_source", "no_expectation")
    have = {_stem(s) for s in selected}
    found = sum(1 for d in must_cite if _stem(d) in have)
    return Score(
        "cites_source", found / len(must_cite), found == len(must_cite), f"{found}/{len(must_cite)}"
    )


def _row(row) -> tuple[str, ...]:
    return tuple(normalize(str(v)) for v in row)


def sql_result(expected: list[list] | None, returned: list[list] | None) -> Score:
    """Row set of the agent's own `run_sql` result against the expected rows (order-free).
    The SQL is not run again here: the score is about what the agent got, and a second query
    path would be a second, unaudited reader of the database."""
    if not expected:
        return _not_run("sql_result", "no_expectation")
    if returned is None:
        return Score("sql_result", 0.0, False, "no_sql_result")
    ok = sorted(map(_row, expected)) == sorted(map(_row, returned))
    return Score("sql_result", 1.0 if ok else 0.0, ok)


def latency_cost(
    ms: int | None, usd: float | None, *, max_ms: int | None, max_usd: float | None
) -> Score:
    if max_ms is None and max_usd is None:
        return _not_run("latency_cost", "no_limit")
    if (max_ms is not None and ms is None) or (max_usd is not None and usd is None):
        return Score("latency_cost", 0.0, False, "not_measured")
    slow = max_ms is not None and ms > max_ms
    costly = max_usd is not None and usd > max_usd
    ok = not (slow or costly)
    return Score(
        "latency_cost",
        1.0 if ok else 0.0,
        ok,
        ",".join(c for c, bad in (("slow", slow), ("costly", costly)) if bad),
    )


def cosine(a: list[float], b: list[float]) -> float:
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        raise ValueError("zero vector")
    return sum(x * y for x, y in zip(a, b, strict=True)) / (na * nb)


def semantic(answer_vec: list[float], expected_vec: list[float], *, threshold: float) -> Score:
    sim = cosine(answer_vec, expected_vec)
    return Score("semantic", max(0.0, sim), sim >= threshold, f"cos={sim:.3f}")


class JudgeParseError(ValueError):
    """The judge model's output has no score in 1-5; nothing is guessed."""


@dataclass(frozen=True)
class JudgeVerdict:
    score: int
    reason: str


_SCORE_LINE = re.compile(r"\bscore\s*[:=]\s*(-?\d+)\b", re.IGNORECASE)


def parse_judge(text: str) -> JudgeVerdict:
    """The rubric asks for JSON {"score": 1-5, "reason": "..."}; a `SCORE: n` line is accepted
    for models that do not keep to JSON. Anything else raises."""
    raw = (text or "").strip()
    score = reason = None
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            score, reason = data.get("score"), data.get("reason")
    except ValueError:
        m = _SCORE_LINE.search(raw)
        if m:
            score = int(m.group(1))
    if isinstance(score, bool) or not isinstance(score, int):
        raise JudgeParseError("judge_output_unreadable")
    if not JUDGE_MIN <= score <= JUDGE_MAX:
        raise JudgeParseError("judge_score_out_of_range")
    return JudgeVerdict(score, str(reason or ""))


def judge_score(verdict: JudgeVerdict, *, pass_min: int) -> Score:
    value = (verdict.score - JUDGE_MIN) / (JUDGE_MAX - JUDGE_MIN)
    return Score("llm_judge", value, verdict.score >= pass_min, f"score={verdict.score}")
