"""05a: the committed OpenAPI draft (`backend/openapi/05a.yaml`) equals what the app serves.

06a (runtime) and 10b-poc-2 (console) consume this file, so it must not drift.
"""

import re
from pathlib import Path

import yaml

from ffcore.api.openapi_export import render
from ffcore.main import app

DRAFT = Path(__file__).resolve().parents[2] / "openapi" / "05a.yaml"
REGENERATE = "python -m ffcore.api.openapi_export 05a > openapi/05a.yaml"
P = "/api/v1/projects/{project_id}/tools"

EXPECTED = {
    P: {"get", "post"},
    P + "/{tool_id}": {"get", "patch", "delete"},
    P + "/{tool_id}/discover": {"post"},
    P + "/{tool_id}/actions/{action_name}": {"patch"},
    P + "/{tool_id}/actions/{action_name}/invoke": {"post"},
    P + "/sql-context": {"post"},
}


def test_05a_openapi_draft_matches_app():
    assert DRAFT.exists(), f"missing {DRAFT}; regenerate with: {REGENERATE}"
    assert DRAFT.read_text(encoding="utf-8") == render("05a"), f"draft drifted; run: {REGENERATE}"


def test_05a_draft_has_the_contracted_operations():
    paths = yaml.safe_load(render("05a"))["paths"]
    assert {path: set(ops) for path, ops in paths.items()} == EXPECTED


def test_05a_app_serves_every_draft_path():
    served = app.openapi()["paths"]
    for path in EXPECTED:
        assert path in served, path


def test_05a_draft_is_english():
    assert not re.search("[çğıöşüÇĞİÖŞÜ]", render("05a"))
