"""06a prompt assembly and context budget (P8, D5, D6), pure functions."""

import re

import pytest

from ffcore.runtime.definition import parse_definition
from ffcore.runtime.prompting import (
    DECLINE_PATTERN,
    Source,
    by_recency,
    fit_history,
    fit_sources,
    plan_budget,
    render_variables,
    user_message,
)

DECLINED = re.compile(DECLINE_PATTERN, re.IGNORECASE)


def _source(n, day, text="x " * 50):
    return Source(n, "kb", f"c{n}", f"d{n}", f"doc{n}.pdf", 1, "B", text, day, 0.5)


@pytest.mark.parametrize(
    ("text", "declined"),
    [
        ("Bu bilgi belgelerde bulunamadı.", True),
        ("Aradığınız madde bulunmamaktadır.", True),
        ("Kaynaklarda bulamadım.", True),
        ("I could not find this in the sources.", True),
        ("Bu konuda yeterli bilgi bulunmaktadır.", False),  # brief 06: must not match
        ("Fesih süresi 30 gündür [1].", False),
    ],
)
def test_06a_2_decline_detection(text, declined):
    assert bool(DECLINED.search(text)) is declined


def test_06a_1_sources_newest_first_before_the_question():
    sources = [_source(1, "2022-01-01T00:00:00+00:00"), _source(2, "2024-05-01T00:00:00+00:00")]
    assert [s.n for s in by_recency(sources)] == [2, 1]
    text = user_message("Soru?", sources)
    assert text.index("doc2.pdf") < text.index("doc1.pdf") < text.index("QUESTION")
    assert "updated 2024-05-01" in text


def test_06a_1_undated_sources_last():
    sources = [_source(1, None), _source(2, "2020-01-01T00:00:00+00:00")]
    assert [s.n for s in by_recency(sources)] == [2, 1]


def _definition(**policy):
    return parse_definition(
        {"model": "chat-default", "system_prompt": "S", "context_policy": policy}
    )


def test_06a_budget_drops_whole_chunks_and_says_so():
    d = _definition(rag_max_tokens=200)
    budget = plan_budget(d, "system", [])
    kept = fit_sources(budget, [_source(i, None, "kelime " * 60) for i in range(1, 6)])
    assert 0 < len(kept) < 5  # whole chunks only, the rest listed
    assert budget.dropped["rag"] == [f"c{i}" for i in range(len(kept) + 1, 6)]
    assert budget.used["rag"] <= 200


def test_06a_budget_history_keeps_the_last_turns_and_counts_drops():
    d = _definition(history_turns=2)
    budget = plan_budget(d, "system", [])
    turns = []
    for i in range(5):
        turns += [{"role": "user", "content": f"q{i}"}, {"role": "assistant", "content": f"a{i}"}]
    kept = fit_history(budget, turns, 2)
    assert [m["content"] for m in kept] == ["q3", "a3", "q4", "a4"]
    assert budget.dropped["history_turns"] == 3


def test_06a_6a_fixed_part_larger_than_context_is_refused():
    d = parse_definition(
        {"model": "chat-default", "system_prompt": "S", "limits": {"context_tokens": 1000}}
    )
    with pytest.raises(ValueError, match="context_configuration_invalid"):
        plan_budget(d, "word " * 2000, [])


def test_06a_variables_rendered_unknown_refused():
    d = parse_definition(
        {
            "model": "chat-default",
            "system_prompt": "S",
            "variables": [{"key": "hospital_name", "label": "H", "default": "Örnek"}],
        }
    )
    assert render_variables("Sen ${hospital_name} asistanısın.", d, {}) == "Sen Örnek asistanısın."
    assert render_variables("${hospital_name}", d, {"hospital_name": "X"}) == "X"
    with pytest.raises(ValueError, match="unknown variables"):
        render_variables("x", d, {"other": "y"})
