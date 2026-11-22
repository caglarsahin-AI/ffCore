"""The extraction call's pure parts (brief 14 "Yazma" 2): the prompt and the answer's schema.

The prompt is the Langfuse prompt `memory_extract` (seed backend/prompts/memory_extract.md,
`platform_rules` pattern: without it the job fails `prompt_unavailable`). The model's answer must
be JSON matching ANSWER_SCHEMA; the seeded `memory-extract` models have no structured output, so
the schema is checked here. Anything else is `memory_extract_invalid`: nothing is written and
the job is not retried (the same turn would give the same answer).
"""

import json
import re
from typing import Any

from jsonschema import Draft202012Validator

from ffcore.memory.store import Candidate
from ffcore.models.memory import KINDS

PROMPT_NAME = "memory_extract"
MAX_ITEMS = 3
TEXT_MAX = 500
OUTPUT_TOKENS = 400

ANSWER_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["items"],
    "properties": {
        "items": {
            "type": "array",
            "maxItems": MAX_ITEMS,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["kind", "text", "confidence"],
                "properties": {
                    "kind": {"enum": list(KINDS)},
                    "text": {"type": "string", "minLength": 1, "maxLength": TEXT_MAX},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "supersedes_id": {"type": ["string", "null"]},
                },
            },
        }
    },
}
_VALIDATOR = Draft202012Validator(ANSWER_SCHEMA)
# Some local models wrap JSON in a ``` fence; only that wrapper is removed, nothing else.
_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


class ExtractInvalid(ValueError):
    code = "memory_extract_invalid"


def turn_text(question: str, answer: str) -> str:
    return f"USER: {question}\nASSISTANT: {answer}"


def known_text(items: list[dict[str, Any]]) -> str:
    if not items:
        return "(none)"
    return "\n".join(f"- id={i['id']} kind={i['kind']}: {i['text']}" for i in items)


def messages(prompt, *, turn: str, known: str) -> list[dict[str, str]]:
    return [{"role": "user", "content": prompt.compile(turn=turn, existing=known)}]


def parse(answer: str) -> list[Candidate]:
    fenced = _FENCE.match(answer or "")
    raw = fenced.group(1) if fenced else (answer or "").strip()
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise ExtractInvalid("the extraction answer is not JSON") from exc
    errors = sorted(_VALIDATOR.iter_errors(data), key=lambda e: list(e.path))
    if errors:
        raise ExtractInvalid(
            f"the extraction answer does not match the schema: {errors[0].message}"
        )
    return [
        Candidate(
            kind=i["kind"],
            text=i["text"].strip(),
            confidence=float(i["confidence"]),
            supersedes_id=i.get("supersedes_id") or None,
        )
        for i in data["items"]
    ]
