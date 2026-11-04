"""09: deterministic scorers, judge output parsing and the stage diagnosis (pure functions)."""

import pytest

from ffcore.evaluation import diagnosis, scorers
from ffcore.evaluation.diagnosis import Candidate, RunFacts

# --- contains / regex / json_schema -------------------------------------------------------


def test_09_contains_normalizes_case_space_and_turkish_dotted_i():
    r = scorers.contains("Fesih  bildirim süresi en az 90 GÜN; İzmir.", ["90 gün", "izmir"])
    assert (r.value, r.passed) == (1.0, True)


def test_09_contains_partial_is_fraction_and_fails():
    r = scorers.contains("90 gün", ["90 gün", "Madde 10.1"])
    assert r.value == 0.5 and r.passed is False


def test_09_contains_without_expectation_is_not_run():
    r = scorers.contains("x", [])
    assert r.status == "not_run" and r.passed is None


def test_09_regex():
    assert scorers.regex("Kod: AB-123", r"[A-Z]{2}-\d{3}").passed is True
    assert scorers.regex("Kod: yok", r"[A-Z]{2}-\d{3}").passed is False


def test_09_json_schema():
    schema = {"type": "object", "required": ["a"], "properties": {"a": {"type": "integer"}}}
    assert scorers.json_schema('{"a": 1}', schema).passed is True
    bad = scorers.json_schema("not json", schema)
    assert bad.passed is False and "json" in bad.comment


# --- cites_source / sql_result / latency_cost / semantic -----------------------------------


def test_09_cites_source_matches_file_stem():
    r = scorers.cites_source(["SZL-2024-011_cihaz-bakim.txt"], ["SZL-2024-011_cihaz-bakim.pdf"])
    assert r.passed is True


def test_09_cites_source_missing_document_fails():
    r = scorers.cites_source(["other.pdf"], ["SZL-2024-011_cihaz-bakim.pdf"])
    assert r.passed is False and r.value == 0.0


def test_09_sql_result_compares_row_sets():
    assert scorers.sql_result([[18]], [[18]]).passed is True
    assert scorers.sql_result([["a", 1], ["b", 2]], [["b", 2], ["a", 1]]).passed is True
    assert scorers.sql_result([[18]], [[17]]).passed is False


def test_09_sql_result_without_tool_result_fails_loud():
    r = scorers.sql_result([[18]], None)
    assert r.passed is False and r.comment == "no_sql_result"


def test_09_latency_cost_limits():
    assert scorers.latency_cost(1200, 0.01, max_ms=2000, max_usd=0.05).passed is True
    assert scorers.latency_cost(2500, 0.01, max_ms=2000, max_usd=0.05).passed is False


def test_09_semantic_cosine_threshold():
    assert scorers.semantic([1.0, 0.0], [1.0, 0.0], threshold=0.8).passed is True
    assert scorers.semantic([1.0, 0.0], [0.0, 1.0], threshold=0.8).passed is False


# --- judge output parsing (no invented score) ----------------------------------------------


@pytest.mark.parametrize("text,score", [('{"score": 4, "reason": "ok"}', 4), ("SCORE: 2", 2)])
def test_09_judge_parse(text, score):
    assert scorers.parse_judge(text).score == score


@pytest.mark.parametrize("text", ["", "very good", '{"score": 7}', '{"score": 0}'])
def test_09_judge_parse_refuses_unreadable_output(text):
    with pytest.raises(scorers.JudgeParseError):
        scorers.parse_judge(text)


# --- stage diagnosis (brief 09 D7; order follows the code: floor before top_k, S5) ----------


def _facts(**kw):
    base = dict(
        status="completed",
        outcome_label="answered",
        answerable=True,
        expected_docs=["A.pdf"],
        candidates=[Candidate("A", below_floor=False)],
        selected=["A.txt"],
    )
    base.update(kw)
    return RunFacts(**base)


def test_09_2b_not_retrieved_when_expected_doc_not_a_candidate():
    f = _facts(candidates=[Candidate("B", below_floor=False)], selected=["B"])
    assert diagnosis.diagnose(f) == "not_retrieved"


def test_09_2b_not_retrieved_regardless_of_answer_label():
    # The judge or the answer label never changes a retrieval failure.
    f = _facts(candidates=[], selected=[], outcome_label="answered")
    assert diagnosis.diagnose(f) == "not_retrieved"


def test_09_below_rerank_floor_when_all_expected_candidates_below_floor():
    f = _facts(candidates=[Candidate("A", below_floor=True)], selected=[])
    assert diagnosis.diagnose(f) == "below_rerank_floor"


def test_09_not_reranked_when_above_floor_but_not_selected():
    f = _facts(candidates=[Candidate("A", below_floor=False)], selected=["B"])
    assert diagnosis.diagnose(f) == "not_reranked"


def test_09_2c_declined():
    assert diagnosis.diagnose(_facts(outcome_label="declined")) == "declined"


def test_09_below_threshold_and_answered():
    assert diagnosis.diagnose(_facts(outcome_label="below_threshold")) == "below_threshold"
    assert diagnosis.diagnose(_facts()) == "answered"


def test_09_unanswerable_held_and_answered():
    held = _facts(answerable=False, expected_docs=[], outcome_label="declined")
    wrong = _facts(answerable=False, expected_docs=[], outcome_label="answered")
    assert diagnosis.diagnose(held) == "unanswerable_held"
    assert diagnosis.diagnose(wrong) == "unanswerable_answered"


def test_09_every_expected_doc_must_pass_a_stage():
    f = _facts(expected_docs=["A.pdf", "C.pdf"], candidates=[Candidate("A", below_floor=False)])
    assert diagnosis.diagnose(f) == "not_retrieved"


def test_09_sql_item_without_documents_skips_retrieval_stages():
    f = _facts(expected_docs=[], candidates=[], selected=[])
    assert diagnosis.diagnose(f) == "answered"


def test_09_unfinished_run_has_no_outcome():
    assert diagnosis.diagnose(_facts(status="failed", outcome_label=None)) is None


def test_09_outcome_vocabulary_is_brief_list():
    assert diagnosis.OUTCOMES == (
        "not_retrieved",
        "not_reranked",
        "below_rerank_floor",
        "declined",
        "below_threshold",
        "answered",
        "unanswerable_held",
        "unanswerable_answered",
    )
