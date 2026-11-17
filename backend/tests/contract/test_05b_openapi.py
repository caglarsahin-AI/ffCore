"""05b: the committed OpenAPI draft (`backend/openapi/05b.yaml`) equals what the app serves.

10c-3 (MCP servers and MCP monitoring screens) consumes this file. The MCP endpoint itself
(`/mcp/{key}/`) is an MCP streamable HTTP endpoint, not a REST route: docs/araclar.md.
"""

import re
from pathlib import Path

import yaml

from ffcore.api.openapi_export import render
from ffcore.main import app

DRAFT = Path(__file__).resolve().parents[2] / "openapi" / "05b.yaml"
REGENERATE = "python -m ffcore.api.openapi_export 05b > openapi/05b.yaml"
P = "/api/v1/projects/{project_id}/mcp-servers"

EXPECTED = {
    P: {"get", "post"},
    P + "/{server_id}": {"get", "patch", "delete"},
    P + "/{server_id}/spec": {"put"},
    P + "/{server_id}/discover": {"post"},
    P + "/{server_id}/test": {"post"},
    P + "/{server_id}/tools": {"post"},
    P + "/{server_id}/calls": {"get"},
}


def test_05b_openapi_draft_matches_app():
    assert DRAFT.exists(), f"missing {DRAFT}; regenerate with: {REGENERATE}"
    assert DRAFT.read_text(encoding="utf-8") == render("05b"), f"draft drifted; run: {REGENERATE}"


def test_05b_draft_has_the_contracted_operations():
    paths = yaml.safe_load(render("05b"))["paths"]
    assert {path: set(ops) for path, ops in paths.items()} == EXPECTED


def test_05b_app_serves_every_draft_path():
    served = app.openapi()["paths"]
    for path in EXPECTED:
        assert path in served, path


def test_05b_mcp_endpoint_is_mounted():
    assert any(getattr(route, "path", None) == "/mcp" for route in app.routes)


def test_05b_draft_is_english():
    assert not re.search("[çğıöşüÇĞİÖŞÜ]", render("05b"))
