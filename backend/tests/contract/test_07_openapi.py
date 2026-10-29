"""07: the committed OpenAPI draft (`backend/openapi/07.yaml`) equals what the app serves.

10b-poc-2 (console approval view) consumes this file, so it must not drift.
"""

import re
from pathlib import Path

import yaml

from ffcore.api.openapi_export import render
from ffcore.main import app

DRAFT = Path(__file__).resolve().parents[2] / "openapi" / "07.yaml"
REGENERATE = "python -m ffcore.api.openapi_export 07 > openapi/07.yaml"
P = "/api/v1/projects/{project_id}/approvals"

EXPECTED = {
    P: {"get"},
    P + "/count": {"get"},
    P + "/{approval_id}": {"get"},
}


def test_07_openapi_draft_matches_app():
    assert DRAFT.exists(), f"missing {DRAFT}; regenerate with: {REGENERATE}"
    assert DRAFT.read_text(encoding="utf-8") == render("07"), f"draft drifted; run: {REGENERATE}"


def test_07_draft_has_the_contracted_operations():
    paths = yaml.safe_load(render("07"))["paths"]
    assert {path: set(ops) for path, ops in paths.items()} == EXPECTED


def test_07_app_serves_every_draft_path():
    served = app.openapi()["paths"]
    for path in EXPECTED:
        assert path in served, path


def test_07_draft_is_english():
    assert not re.search("[çğıöşüÇĞİÖŞÜ]", render("07"))
