"""04a: the committed OpenAPI draft (`backend/openapi/04a.yaml`) equals what the app serves.

05a (mcp-search), 06a (runtime) and 10b (console) consume this file, so it must not drift.
"""

import re
from pathlib import Path

from ffcore.api.openapi_export import render
from ffcore.main import app

DRAFT = Path(__file__).resolve().parents[2] / "openapi" / "04a.yaml"
REGENERATE = "python -m ffcore.api.openapi_export 04a > openapi/04a.yaml"
KB = "/api/v1/projects/{project_id}/knowledge-bases"

EXPECTED = {
    KB: {"get", "post"},
    KB + "/{kb_id}": {"get", "patch", "delete"},
    KB + "/{kb_id}/documents": {"get", "post"},
    KB + "/{kb_id}/documents/{document_id}": {"get", "delete"},
    KB + "/{kb_id}/reindex": {"post"},
    KB + "/{kb_id}/search": {"post"},
    KB + "/{kb_id}/test-query": {"post"},
    "/internal/embed": {"post"},
    "/readyz": {"get"},
}


def _paths(spec_text: str) -> dict:
    import yaml

    return yaml.safe_load(spec_text)["paths"]


def test_04a_20_openapi_draft_matches_app():
    assert DRAFT.exists(), f"missing {DRAFT}; regenerate with: {REGENERATE}"
    assert DRAFT.read_text(encoding="utf-8") == render("04a"), f"draft drifted; run: {REGENERATE}"


def test_04a_20_draft_has_the_contracted_operations():
    paths = _paths(render("04a"))
    assert {path: set(ops) for path, ops in paths.items()} == EXPECTED


def test_04a_20_app_serves_every_draft_path():
    served = app.openapi()["paths"]
    for path, ops in EXPECTED.items():
        assert path in served, path
        assert ops <= set(served[path]), path


def test_04a_20_draft_text_is_english():
    assert not re.search("[çğıöşüÇĞİÖŞÜ]", render("04a"))


def test_04a_20_03a_draft_unchanged_by_04a_routes():
    # The 03a contract is frozen for its consumers; 04a routes live in their own draft.
    paths = _paths(render("03a"))
    assert not any("knowledge-bases" in path or path.startswith("/internal") for path in paths)


def test_04a_20_search_carries_run_id_header():
    # C12: X-Run-Id ties a search to a run in kb_queries.
    op = _paths(render("04a"))[KB + "/{kb_id}/search"]["post"]
    headers = {p["name"].lower() for p in op.get("parameters", []) if p["in"] == "header"}
    assert "x-run-id" in headers
