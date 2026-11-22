"""14: the committed OpenAPI draft (`backend/openapi/14.yaml`) equals what the app serves, and
no schema an administrator reads carries memory text."""

from pathlib import Path

import yaml

from ffcore.api.openapi_export import render

DRAFT = Path(__file__).resolve().parents[2] / "openapi" / "14.yaml"
REGENERATE = "python -m ffcore.api.openapi_export 14 > openapi/14.yaml"
P = "/api/v1/projects/{project_id}/memories"

EXPECTED = {
    P: {"get", "post", "delete"},
    P + "/{memory_id}": {"patch", "delete"},
    P + "/opt-out": {"get", "put", "delete"},
    P + "/stats": {"get"},
    P + "/settings": {"get", "put"},
    "/internal/memories/recall": {"post"},
    "/internal/memories/related": {"post"},
    "/internal/memories/candidates": {"post"},
}


def test_14_openapi_draft_matches_app():
    assert DRAFT.exists(), f"missing {DRAFT}; regenerate with: {REGENERATE}"
    assert DRAFT.read_text(encoding="utf-8") == render("14"), f"draft drifted; run: {REGENERATE}"


def test_14_openapi_paths():
    spec = yaml.safe_load(render("14"))
    assert {p: set(m) for p, m in spec["paths"].items()} == EXPECTED


def test_14_statistics_schemas_have_no_text():
    schemas = yaml.safe_load(render("14"))["components"]["schemas"]
    for name in ("MemoryStats", "UserStats", "MemorySettingsOut"):
        assert "text" not in schemas[name]["properties"], name
