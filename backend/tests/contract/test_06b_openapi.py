"""06b: the committed OpenAPI draft (`backend/openapi/06b.yaml`) equals what the app serves,
and adding 06b leaves every earlier draft (and the console types made from them) unchanged."""

from pathlib import Path

import yaml

from ffcore.api.openapi_export import PACKAGES, render

DRAFT = Path(__file__).resolve().parents[2] / "openapi" / "06b.yaml"
REGENERATE = "python -m ffcore.api.openapi_export 06b > openapi/06b.yaml"
P = "/api/v1/projects/{project_id}"

EXPECTED = {
    "/v1/chat/completions": {"post"},
    "/v1/models": {"get"},
    P + "/agents/{agent_id}/manifest": {"get"},
    P + "/agents/import": {"post"},
    "/internal/knowledge-bases/{kb_id}/key-search": {"post"},
}


def test_06b_0_openapi_draft_matches_app():
    assert DRAFT.exists(), f"missing {DRAFT}; regenerate with: {REGENERATE}"
    assert DRAFT.read_text(encoding="utf-8") == render("06b"), f"draft drifted; run: {REGENERATE}"


def test_06b_0_draft_has_the_contracted_operations():
    paths = yaml.safe_load(render("06b"))["paths"]
    assert {p: set(ops) for p, ops in paths.items()} == EXPECTED


def test_06b_0_other_drafts_unchanged_by_06b():
    for package in PACKAGES:
        if package == "06b":
            continue
        committed = DRAFT.parent / f"{package}.yaml"
        assert committed.read_text(encoding="utf-8") == render(package), package
