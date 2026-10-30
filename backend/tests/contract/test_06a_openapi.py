"""06a: the committed OpenAPI draft (`backend/openapi/06a.yaml`) equals what the app serves.

10b-poc-2 (agent wizard, runs, approvals) and 07 consume this file, so it must not drift.
"""

from pathlib import Path

import yaml

from ffcore.api.openapi_export import render

DRAFT = Path(__file__).resolve().parents[2] / "openapi" / "06a.yaml"
REGENERATE = "python -m ffcore.api.openapi_export 06a > openapi/06a.yaml"
P = "/api/v1/projects/{project_id}"

EXPECTED = {
    P + "/agents": {"get", "post"},
    P + "/agents/{agent_id}": {"get", "patch", "delete"},
    P + "/agents/{agent_id}/versions": {"get", "post"},
    P + "/agents/{agent_id}/versions/{version}": {"get", "put"},
    P + "/agents/{agent_id}/publish": {"post"},
    P + "/agents/{agent_id}/rollback": {"post"},
    P + "/agents/{agent_key}/runs": {"post"},
    P + "/runs": {"get"},
    P + "/runs/{run_id}": {"get"},
    P + "/runs/{run_id}/events": {"get"},
    P + "/runs/{run_id}/stream": {"get"},
    P + "/runs/{run_id}/resume": {"post"},
    P + "/runs/{run_id}/cancel": {"post"},
    # F9 (K-06a-0005), additive
    P + "/runs/{run_id}/feedback": {"post"},
}


def test_06a_0_openapi_draft_matches_app():
    assert DRAFT.exists(), f"missing {DRAFT}; regenerate with: {REGENERATE}"
    assert DRAFT.read_text(encoding="utf-8") == render("06a"), f"draft drifted; run: {REGENERATE}"


def test_06a_0_draft_has_the_contracted_operations():
    paths = yaml.safe_load(render("06a"))["paths"]
    assert {p: set(ops) for p, ops in paths.items()} == EXPECTED


def test_06a_0_streams_are_event_streams():
    paths = yaml.safe_load(render("06a"))["paths"]
    for path, method in [
        (P + "/agents/{agent_key}/runs", "post"),
        (P + "/runs/{run_id}/stream", "get"),
    ]:
        content = paths[path][method]["responses"]["200"]["content"]
        assert set(content) == {"text/event-stream"}, path


def test_06a_0_other_drafts_unchanged_by_06a():
    # Adding a package never changes an earlier draft.
    for package in ("03a", "04a", "08"):
        committed = DRAFT.parent / f"{package}.yaml"
        assert committed.read_text(encoding="utf-8") == render(package), package
