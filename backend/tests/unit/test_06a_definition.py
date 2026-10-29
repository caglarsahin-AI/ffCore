"""06a acceptance 15 and C8: agent definitions are validated, 13a's templates pass."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ffcore.runtime.definition import SCHEMA_VERSION, AgentDefinition, parse_definition

TEMPLATES = Path(__file__).resolve().parents[3] / "data" / "samples" / "agents"
MINIMAL = {"model": "chat-default", "system_prompt": "You answer from the documents."}


def _codes(exc: ValidationError) -> str:
    return " ".join(str(err["msg"]) for err in exc.errors())


@pytest.mark.parametrize("name", ["sozlesme-asistani", "veri-soru-cevap", "karma-asistan"])
def test_06a_15_templates_validate(name):
    template = json.loads((TEMPLATES / f"{name}.json").read_text(encoding="utf-8"))
    definition = parse_definition(template["definition"])
    assert definition.schema_version == SCHEMA_VERSION


def test_06a_15_missing_schema_version_is_version_1():
    assert parse_definition(MINIMAL).schema_version == 1


def test_06a_15_unknown_field_rejected():
    with pytest.raises(ValidationError) as exc:
        parse_definition({**MINIMAL, "webhook_url": "http://x"})
    assert "extra" in _codes(exc.value).lower() or "webhook_url" in str(exc.value)


def test_c8_removed_fields_stay_removed():
    # C21: webhook_url, budget_usd, raw_output_tools are not definition fields.
    for field in ("webhook_url", "budget_usd", "raw_output_tools"):
        assert field not in AgentDefinition.model_fields


@pytest.mark.parametrize(
    ("patch", "code"),
    [
        ({"system_prompt": None}, "prompt_source"),
        ({"langfuse_prompt": {"name": "x"}}, "prompt_source"),
        ({"answer_rules": {"verify": True}}, "verify_not_supported"),
        (
            {"knowledge": [{"kb_key": "k", "mode": "always", "filter": {"scope": ["jira:X"]}}]},
            "knowledge_filter_not_supported",
        ),
        (
            {"answer_rules": {"confidence_formula": "sentence_max"}},
            "confidence_formula_not_supported",
        ),
        (
            {
                "tools": [{"tool_key": "mcp-sql", "actions": ["run_sql"]}],
                "approval": {"actions": ["mcp-sql.drop"]},
            },
            "approval_action_unknown",
        ),
        ({"limits": {"output_tokens": 900}}, "output_reserve_too_small"),
        ({"structured_output": {"type": "nonsense"}}, "structured_output_invalid"),
        (
            {"variables": [{"key": "a", "label": "A"}, {"key": "a", "label": "B"}]},
            "variable_duplicate",
        ),
    ],
)
def test_06a_15_inconsistent_definitions_are_coded(patch, code):
    with pytest.raises(ValidationError) as exc:
        parse_definition({**MINIMAL, **patch})
    assert code in _codes(exc.value)


def test_06a_15_user_role_never_approves():
    with pytest.raises(ValidationError):
        parse_definition({**MINIMAL, "approval": {"actions": [], "assign_to": "user"}})


def test_06a_15_model_key_pattern_matches_the_api():
    from ffcore.api.schemas import MODEL_KEY_PATTERN as API_PATTERN
    from ffcore.runtime.definition import MODEL_KEY_PATTERN

    assert MODEL_KEY_PATTERN == API_PATTERN


def test_06a_approval_assign_to_defaults_to_analyst():
    # Brief 07 (K-07-0002 S7): the default approver is analyst, never admin by default.
    parsed = parse_definition(
        {
            **MINIMAL,
            "tools": [{"tool_key": "mcp-sql", "actions": ["run_sql"]}],
            "approval": {"actions": ["mcp-sql.run_sql"]},
        }
    )
    assert parsed.approval.assign_to == "analyst"
