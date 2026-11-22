"""14: the extraction answer's schema (brief 14 "Yazma" 2: JSON, 0-3 items) and the prompt."""

import json

import pytest

from ffcore.memory import extract


def _answer(*items) -> str:
    return json.dumps({"items": list(items)})


def test_14_parse_reads_up_to_three_items():
    candidates = extract.parse(
        _answer(
            {"kind": "profile", "text": " Kardiyoloji bölüm sorumlusu. ", "confidence": 0.9},
            {"kind": "preference", "text": "TL ister.", "confidence": 1, "supersedes_id": "abc"},
        )
    )
    assert [(c.kind, c.text, c.confidence, c.supersedes_id) for c in candidates] == [
        ("profile", "Kardiyoloji bölüm sorumlusu.", 0.9, None),
        ("preference", "TL ister.", 1.0, "abc"),
    ]


def test_14_parse_empty_list_is_nothing_learned():
    assert extract.parse(_answer()) == []


def test_14_parse_accepts_only_a_json_fence_around_the_answer():
    fenced = "```json\n" + _answer({"kind": "fact", "text": "x", "confidence": 0.7}) + "\n```"
    assert [c.kind for c in extract.parse(fenced)] == ["fact"]
    with pytest.raises(extract.ExtractInvalid):
        extract.parse("Here you go: " + _answer())


@pytest.mark.parametrize(
    "answer",
    [
        "not json",
        "[]",
        json.dumps({"items": [{"kind": "rumour", "text": "x", "confidence": 0.9}]}),
        json.dumps({"items": [{"kind": "fact", "text": "", "confidence": 0.9}]}),
        json.dumps({"items": [{"kind": "fact", "text": "x", "confidence": 1.5}]}),
        json.dumps({"items": [{"kind": "fact", "text": "x"}]}),
        json.dumps({"items": [{"kind": "fact", "text": "x", "confidence": 0.9, "extra": 1}]}),
        json.dumps({"items": [{"kind": "fact", "text": "x", "confidence": 0.9}] * 4}),
        json.dumps({"items": [{"kind": "fact", "text": "x" * 501, "confidence": 0.9}]}),
    ],
)
def test_14_parse_refuses_what_the_schema_does_not_allow(answer):
    with pytest.raises(extract.ExtractInvalid) as raised:
        extract.parse(answer)
    assert raised.value.code == "memory_extract_invalid"


class _Prompt:
    def __init__(self):
        self.values = None

    def compile(self, **values):
        self.values = values
        return "PROMPT"


def test_14_messages_carry_the_turn_and_the_known_items_with_ids():
    prompt = _Prompt()
    known = extract.known_text([{"id": "m1", "kind": "profile", "text": "Bölüm sorumlusu."}])
    out = extract.messages(prompt, turn=extract.turn_text("Soru", "Cevap"), known=known)
    assert out == [{"role": "user", "content": "PROMPT"}]
    assert prompt.values == {
        "turn": "USER: Soru\nASSISTANT: Cevap",
        "existing": "- id=m1 kind=profile: Bölüm sorumlusu.",
    }
    assert extract.known_text([]) == "(none)"


def test_14_seed_prompt_has_the_two_variables():
    from pathlib import Path

    seed = Path(__file__).resolve().parents[2] / "prompts" / f"{extract.PROMPT_NAME}.md"
    text = seed.read_text(encoding="utf-8")
    assert "{{turn}}" in text and "{{existing}}" in text
