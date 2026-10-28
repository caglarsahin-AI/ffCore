"""08-lite: the committed OpenAPI draft (`backend/openapi/08.yaml`) equals what the app serves.

06a (runtime hooks), 06b (facade) and 10 (console) consume this file, so it must not drift.
"""

import re
from pathlib import Path

import yaml

from ffcore.api.openapi_export import render
from ffcore.main import app

DRAFT = Path(__file__).resolve().parents[2] / "openapi" / "08.yaml"
REGENERATE = "python -m ffcore.api.openapi_export 08 > openapi/08.yaml"
P = "/api/v1/projects/{project_id}"

EXPECTED = {
    P + "/pii-policies": {"get", "post"},
    P + "/pii-policies/{policy_id}": {"get", "patch", "delete"},
    P + "/guardrail-policies": {"get", "post"},
    P + "/guardrail-policies/{policy_id}": {"get", "patch", "delete"},
    P + "/guardrails/test": {"post"},
    "/api/v1/internal/guardrails/evaluate": {"post"},
}


def _paths(spec_text: str) -> dict:
    return yaml.safe_load(spec_text)["paths"]


def test_08_22_openapi_draft_matches_app():
    assert DRAFT.exists(), f"missing {DRAFT}; regenerate with: {REGENERATE}"
    assert DRAFT.read_text(encoding="utf-8") == render("08"), f"draft drifted; run: {REGENERATE}"


def test_08_22_draft_has_the_contracted_operations():
    paths = _paths(render("08"))
    assert {path: set(ops) for path, ops in paths.items()} == EXPECTED


def test_08_22_app_serves_every_draft_path():
    served = app.openapi()["paths"]
    for path, ops in EXPECTED.items():
        assert path in served, path
        assert ops <= set(served[path]), path


def test_08_22_draft_text_is_english():
    assert not re.search("[çğıöşüÇĞİÖŞÜ]", render("08"))


def test_08_22_03a_draft_unchanged_by_08_routes():
    paths = _paths(render("03a"))
    assert not any("guardrail" in p or "pii-policies" in p for p in paths)


def test_c4_decision_contract_in_draft():
    # CONTRACTS C4: stage names and order, action values, the Decision shape.
    schemas = yaml.safe_load(render("08"))["components"]["schemas"]
    stages = schemas["EvaluateRequest"]["properties"]["stage"]["enum"]
    assert stages == [
        "prompt.pre",
        "input.pre",
        "output.pre",
        "output.stream.delta",
        "tool.pre",
        "tool.post",
        "egress",
    ]
    decision = schemas["DecisionOut"]["properties"]
    assert decision["action"]["enum"] == [
        "allow",
        "block",
        "redact",
        "mask",
        "tokenize",
        "warn",
        "log",
    ]
    assert {"action", "text_out", "message", "reference_id", "events"} <= set(decision)
