"""19 şart 5: the S1 report never lands in the repository (`make eval` EVAL_OUT, gate check)."""

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


er = _load("eval_report")
gate = _load("m3_gate_check")
NOW = datetime(2026, 11, 1, 9, 30, tzinfo=UTC)
IN_REPO_SET = REPO / "data" / "samples" / "eval" / "sozlesme-33.json"


def test_19_s5_eval_out_required_for_a_dataset_outside_the_repo(tmp_path):
    with pytest.raises(SystemExit) as err:
        er.resolve_out(tmp_path / "s1.jsonl", out=None, out_dir=None, now=NOW)
    assert "eval_out_required" in str(err.value)


def test_19_s5_eval_out_outside_repo(tmp_path):
    out = er.resolve_out(tmp_path / "s1.jsonl", out=None, out_dir=str(tmp_path / "r"), now=NOW)
    assert out == tmp_path / "r" / "eval-20261101-0930.md"


@pytest.mark.parametrize("target", ["docs", "eval", "data/samples"])
def test_19_s5_eval_out_inside_repo_only_under_eval_results(tmp_path, target):
    with pytest.raises(SystemExit) as err:
        er.resolve_out(tmp_path / "s1.jsonl", out=None, out_dir=str(REPO / target), now=NOW)
    assert "eval_out_inside_repo" in str(err.value)
    with pytest.raises(SystemExit):
        er.resolve_out(IN_REPO_SET, out=str(REPO / target / "x.md"), out_dir=None, now=NOW)


def test_19_s5_in_repo_dataset_keeps_the_13b_default():
    out = er.resolve_out(IN_REPO_SET, out=None, out_dir=None, now=NOW)
    assert out == REPO / "eval" / "results" / "eval-20261101-0930.md"


def test_19_s5_repo_gate_check():
    assert gate.violations(["backend/ffcore/cli.py", "docs/demo.md", ".gitignore"]) == []
    assert gate.violations(sorted(gate.ALLOWED)) == []
    found = gate.violations(
        [
            "eval/results/eval-20261101-0930.md",
            "data/s1/questions.jsonl",
            "docs/eval-20261101-0930.md",
            "eval/scenario1/questions.jsonl",
        ]
    )
    assert len(found) == 4


def test_19_s5_gitignore_covers_eval_results():
    assert "eval/results/" in (REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
