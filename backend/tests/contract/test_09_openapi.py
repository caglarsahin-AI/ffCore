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
    P + "/eval-suites/{suite_id}/items/from-run/{run_id}": {"post"},  # 09-2 D3
    P + "/eval-runs/compare": {"get"},  # 09-2 D1
    P + "/eval-runs/{eval_run_id}": {"get"},
    P + "/eval-runs/{eval_run_id}/items": {"get"},  # 10c-2 D8 (FOLLOWUP-185)
    P + "/eval-runs/{eval_run_id}/cancel": {"post"},
    P + "/eval-runs/{eval_run_id}/stream": {"get"},
}


def test_09_openapi_draft_matches_app():
    assert DRAFT.exists(), f"missing {DRAFT}; regenerate with: {REGENERATE}"
    assert DRAFT.read_text(encoding="utf-8") == render("09"), f"draft drifted; run: {REGENERATE}"


def test_09_openapi_paths():
    spec = yaml.safe_load(render("09"))
    assert {p: set(m) for p, m in spec["paths"].items()} == EXPECTED


def test_09_2_r1_minor10_from_run_documents_its_upstream_errors():
    # 503: the NER the egress policy needs (`ner_unavailable`, `ner_not_configured`) or Langfuse
    # missing; 502: the Langfuse call failed.
    spec = yaml.safe_load(render("09"))
    post = spec["paths"][P + "/eval-suites/{suite_id}/items/from-run/{run_id}"]["post"]
    assert {"502", "503"} <= set(post["responses"]), sorted(post["responses"])
