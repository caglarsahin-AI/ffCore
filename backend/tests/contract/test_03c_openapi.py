"""03c: the committed OpenAPI draft (`backend/openapi/03c.yaml`) equals what the app serves.

06b (facade keys, quotas) and 10c (keys, limits, usage screens) consume this file.
"""

from pathlib import Path

import yaml

from ffcore.api.openapi_export import render
from ffcore.main import app

DRAFT = Path(__file__).resolve().parents[2] / "openapi" / "03c.yaml"
REGENERATE = "python -m ffcore.api.openapi_export 03c > openapi/03c.yaml"
P = "/api/v1/projects/{project_id}"

EXPECTED = {
    P + "/api-keys": {"get", "post"},
    P + "/api-keys/{key_id}": {"get", "patch"},
    P + "/api-keys/{key_id}/revoke": {"post"},
    P + "/quotas": {"get", "post"},
    P + "/quotas/{quota_id}": {"get", "patch", "delete"},
    P + "/usage": {"get"},
}


def test_03c_openapi_draft_matches_app():
    assert DRAFT.exists(), f"missing {DRAFT}; regenerate with: {REGENERATE}"
    assert DRAFT.read_text(encoding="utf-8") == render("03c"), f"draft drifted; run: {REGENERATE}"


def test_03c_draft_has_the_contracted_operations():
    paths = yaml.safe_load(render("03c"))["paths"]
    assert {path: set(ops) for path, ops in paths.items()} == EXPECTED


def test_03c_app_serves_every_draft_path():
    served = app.openapi()["paths"]
    for path in EXPECTED:
        assert path in served, path


def test_03c_descriptions_english():
    text = render("03c")
    assert not set("çğıöşüÇĞİÖŞÜ") & set(text)
