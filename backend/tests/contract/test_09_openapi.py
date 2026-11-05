"""09: the committed OpenAPI draft (`backend/openapi/09.yaml`) equals what the app serves."""

from pathlib import Path

import yaml

from ffcore.api.openapi_export import render

DRAFT = Path(__file__).resolve().parents[2] / "openapi" / "09.yaml"
REGENERATE = "python -m ffcore.api.openapi_export 09 > openapi/09.yaml"
P = "/api/v1/projects/{project_id}"

EXPECTED = {
    P + "/eval-suites": {"get", "post"},
    P + "/eval-suites/{suite_id}": {"get", "patch", "delete"},
    P + "/eval-suites/{suite_id}/run": {"post"},
    P + "/eval-suites/{suite_id}/runs": {"get"},
    P + "/eval-runs/{eval_run_id}": {"get"},
    P + "/eval-runs/{eval_run_id}/cancel": {"post"},
    P + "/eval-runs/{eval_run_id}/stream": {"get"},
}


def test_09_openapi_draft_matches_app():
    assert DRAFT.exists(), f"missing {DRAFT}; regenerate with: {REGENERATE}"
    assert DRAFT.read_text(encoding="utf-8") == render("09"), f"draft drifted; run: {REGENERATE}"


def test_09_openapi_paths():
    spec = yaml.safe_load(render("09"))
    assert {p: set(m) for p, m in spec["paths"].items()} == EXPECTED
