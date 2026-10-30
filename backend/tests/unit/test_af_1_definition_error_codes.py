"""FOLLOWUP-105: a definition refused at save answers 422 invalid_request_error with its own code
(C8, docs/agentlar.md), not a bare validation_error; other validation errors stay as they were."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from ffcore.core.errors import install_error_handlers
from ffcore.runtime.definition import AgentDefinition

MINIMAL = {"model": "chat-default", "system_prompt": "You answer from the documents."}
KB = {"kb_key": "k", "mode": "always"}
TOOL = {"tool_key": "mcp-sql", "actions": ["run_sql"]}


class _Body(BaseModel):
    # The same shape as the agent version body (api/agents_schemas.py).
    name: str = Field(default="x", min_length=1)
    definition: AgentDefinition


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = FastAPI()
    install_error_handlers(app)

    @app.put("/definition")
    def put(body: _Body) -> dict:
        return {"ok": True}

    return TestClient(app)


CASES = [
    ({"system_prompt": None}, "prompt_source"),
    ({"variables": [{"key": "a", "label": "A"}, {"key": "a", "label": "B"}]}, "variable_duplicate"),
    ({"system_prompt": "Hello {{who}}"}, "variable_undefined"),
    ({"knowledge": [KB, KB]}, "knowledge_duplicate"),
    (
        {"knowledge": [{**KB, "filter": {"scope": ["jira:X"]}}]},
        "knowledge_filter_not_supported",
    ),
    ({"tools": [TOOL, TOOL]}, "tool_duplicate"),
    ({"tools": [TOOL], "approval": {"actions": ["mcp-sql.drop"]}}, "approval_action_unknown"),
    ({"answer_rules": {"verify": True}}, "verify_not_supported"),
    ({"answer_rules": {"confidence_formula": "sentence_max"}}, "confidence_formula_not_supported"),
    ({"limits": {"output_tokens": 900}}, "output_reserve_too_small"),
    ({"structured_output": {"type": "nonsense"}}, "structured_output_invalid"),
]


@pytest.mark.parametrize(("patch", "code"), CASES, ids=[c for _, c in CASES])
def test_af_1_definition_error_codes(client, patch, code):
    response = client.put("/definition", json={"definition": {**MINIMAL, **patch}})
    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["type"] == "invalid_request_error"
    assert error["code"] == code
    assert error["message"].startswith("definition: "), error["message"]


def test_af_1b_other_validation_unchanged(client):
    response = client.put("/definition", json={"name": "", "definition": MINIMAL})
    assert response.status_code == 422
    assert response.json()["error"] == {
        "message": "Invalid request: body.name",
        "type": "invalid_request_error",
        "code": "validation_error",
    }
    unknown = client.put("/definition", json={"definition": {**MINIMAL, "webhook_url": "x"}})
    assert unknown.json()["error"]["code"] == "validation_error"
