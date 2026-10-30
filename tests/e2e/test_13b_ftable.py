"""13b: the F table that `make e2e` prints (K-13b-0001 S2). Pure functions, no stack: results
of a pytest run become one row per plan/18 use case with passed / failed / NOT_RUN and the
reasons; known product findings are labelled from known_findings.json."""

import subprocess
from pathlib import Path

import ftable  # tests/e2e is on sys.path (rootdir-based import, no __init__)

KNOWN = {"test_18_f10_4_direct_ids_are_404": {"followup": "FOLLOWUP-103", "note": "403 not 404"}}


def result(nodeid, outcome, reason=""):
    return ftable.Result(nodeid=nodeid, outcome=outcome, reason=reason)


def test_13b_ftable_1_rows_from_test_names():
    assert ftable.row_of("tests/e2e/scenarios/test_x.py::test_18_f3_9_write_attempts") == "F3"
    assert ftable.row_of("x.py::test_18_f10_4_direct_ids_are_404") == "F10"
    assert ftable.row_of("x.py::test_18_f11_5_poison_arrives_as_data[P1]") == "F11"
    assert ftable.row_of("tests/e2e/negative/test_n.py::test_13b_neg_auth_1_x") == "Negative"
    assert ftable.row_of("x.py::test_18_env_1_overlay") == "Setup"
    assert ftable.row_of("x.py::test_18_seed_5_client") == "Setup"
    # 13b's own tooling tests (seed, eval report) are setup rows, never "Other"
    assert ftable.row_of("x.py::test_13b_5_same_file_is_not_uploaded_again") == "Setup"
    assert ftable.row_of("x.py::test_13b_7_report_shape") == "Setup"


def test_13b_ftable_2_row_status():
    results = [
        result("a.py::test_18_f1_1_sources", "passed"),
        result("a.py::test_18_f1_2_declined", "skipped", "NOT_RUN: gerçek model"),
        result("a.py::test_18_f10_4_direct_ids_are_404", "failed"),
        result("a.py::test_18_f10_5_listing", "passed"),
        result("a.py::test_18_f12_1_outage[x]", "skipped", "NOT_RUN: compose runner"),
        result("a.py::test_18_f3_9_writes", "failed"),
    ]
    rows = {r.row: r for r in ftable.summarize(results, KNOWN)}
    assert rows["F1"].status == "passed" and rows["F1"].not_run == 1
    assert rows["F10"].status == "failed (known: FOLLOWUP-103)"
    assert rows["F12"].status == "NOT_RUN"
    assert rows["F3"].status == "failed"  # an unknown failure is never hidden behind a known one


def test_13b_ftable_3_markdown_lists_failures_and_reasons():
    results = [
        result("a.py::test_18_f10_4_direct_ids_are_404", "failed"),
        result("a.py::test_18_f12_1_outage[a]", "skipped", "NOT_RUN: compose runner"),
        result("a.py::test_18_f12_1_outage[b]", "skipped", "NOT_RUN: compose runner"),
    ]
    text = ftable.markdown(ftable.summarize(results, KNOWN))
    assert "| F10 | failed (known: FOLLOWUP-103) | 0 | 1 | 0 |" in text
    assert "test_18_f10_4_direct_ids_are_404 (FOLLOWUP-103: 403 not 404)" in text
    assert text.count("NOT_RUN: compose runner") == 1  # a reason is listed once per row
    assert text.splitlines()[0].startswith("| Use case |")


def test_13b_ftable_4_rows_in_plan_order():
    results = [result(f"a.py::test_18_f{n}_1_x", "passed") for n in (13, 2, 10, 1)]
    results.append(result("n.py::test_13b_neg_auth_1_x", "passed"))
    assert [r.row for r in ftable.summarize(results, {})] == ["F1", "F2", "F10", "F13", "Negative"]


def test_13b_ftable_5_known_findings_file_names_real_tests():
    """Every entry of known_findings.json names a test that exists, with a FOLLOWUP id. Empty is
    a valid state: FOLLOWUP-103 and 108 are closed (main 298cbb4, 3f2bc31), so no finding is
    known; a new one is added with its FOLLOWUP id when a run shows it."""
    known = ftable.load_known()
    names = ftable.collected_test_names()
    assert isinstance(known, dict)
    for name, entry in known.items():
        assert name in names, name
        assert entry["followup"].startswith("FOLLOWUP-") and entry["note"], name


def test_13b_6_make_e2e_runs_every_e2e_test_and_writes_the_f_table():
    """13b acceptance 6: `make e2e` runs tests/e2e (scenarios + negative) with the stack flag and
    writes the F table under eval/results/, which git ignores (a run result, not a source)."""
    repo = Path(__file__).resolve().parents[2]
    dry = subprocess.run(
        ["make", "-n", "e2e"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout
    assert "RUN_E2E_SCENARIOS=1" in dry and "pytest tests/e2e " in dry, dry
    assert "--f-table eval/results/e2e-" in dry, dry
    # The worktree's .git points at a host path, so git cannot run in the tools container.
    ignore = (repo / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "eval/results/" in ignore, "eval/results/ must be in .gitignore"
