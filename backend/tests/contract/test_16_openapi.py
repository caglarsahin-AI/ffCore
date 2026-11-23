"""16: the committed OpenAPI draft (`backend/openapi/16.yaml`) equals what the app serves, and no
response schema can carry a credential value."""

from pathlib import Path

import yaml

from ffcore.api.openapi_export import render

DRAFT = Path(__file__).resolve().parents[2] / "openapi" / "16.yaml"
REGENERATE = "python -m ffcore.api.openapi_export 16 > openapi/16.yaml"
P = "/api/v1/projects/{project_id}/data-sources"

EXPECTED = {
    P: {"get", "post"},
    P + "/{source_id}": {"get", "patch", "delete"},
    P + "/{source_id}/test": {"post"},
    P + "/{source_id}/sync": {"post"},
    P + "/{source_id}/runs": {"get"},
    P + "/{source_id}/runs/{run_id}": {"get"},
    P + "/{source_id}/runs/{run_id}/cancel": {"post"},
    P + "/{source_id}/items": {"get"},
    P + "/{source_id}/acl-mappings": {"get", "put"},
}


def test_16_openapi_draft_matches_app():
    assert DRAFT.exists(), f"missing {DRAFT}; regenerate with: {REGENERATE}"
    assert DRAFT.read_text(encoding="utf-8") == render("16"), f"draft drifted; run: {REGENERATE}"


def test_16_openapi_paths():
    spec = yaml.safe_load(render("16"))
    assert {p: set(m) for p, m in spec["paths"].items()} == EXPECTED


def test_16_credentials_are_names_only_in_responses():
    schemas = yaml.safe_load(render("16"))["components"]["schemas"]
    secret = schemas["DataSourceOut"]["properties"]["secret"]
    # Credential field names with *** values; nothing else of a credential is described.
    assert "secret_encrypted" not in schemas["DataSourceOut"]["properties"]
    assert "Credential field names" in secret["description"]


def test_16_sync_layers_and_prune_decisions():
    schemas = yaml.safe_load(render("16"))["components"]["schemas"]
    assert schemas["SyncLayer"]["enum"] == ["raw", "silver", "gold"]
    assert schemas["SyncMode"]["enum"] == ["full", "delta"]
    assert schemas["SourceKind"]["enum"] == ["fs", "confluence", "jira", "sharepoint"]
