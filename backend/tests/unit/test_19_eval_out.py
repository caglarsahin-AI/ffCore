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


# --- S1 without PRSIM (KARARLAR "M3 korpus kapsamı"): excluded on both sides, n/N in the report ---


def _item(i, sources, answerable=True):
    return {
        "id": f"s1-{i:03d}",
        "input": {"message": "-", "variables": {}},
        "expected_output": {"must_contain": [], "must_cite": ["1001"]},
        "metadata": {"answerable": answerable, "style": "dogrudan", "sources": sources},
    }


def test_19_s5_exclude_sources_drops_prsim_items():
    items = [_item(1, ["confluence:OCR"]), _item(2, ["jira:PRSIM"]), _item(3, [])]
    kept, excluded = er.select_items(items, ["prsim"])
    assert [i["id"] for i in kept] == ["s1-001", "s1-003"]
    assert excluded == {"prsim": 1}
    assert er.select_items(items, []) == (items, {})


def test_19_s5_report_states_n_of_total_and_warmup():
    results = [
        er.ItemResult(
            "s1-001",
            "dogrudan",
            True,
            False,
            "answered",
            "completed",
            {"contains": True, "cites_source": True, "llm_judge": None},
            100.0,
            2,
        ),
    ]
    meta = {
        "dataset": "s1",
        "agent": "a",
        "model": "qwen3.5:35b cpu",
        "total": 50,
        "excluded": {"prsim": 9},
        "warmup": [200.0, 150.0],
    }
    text = er.markdown(meta, results)
    assert "Scored items: 1/50 (excluded by source: prsim 9)" in text
    assert "Warmup runs (not scored, not in times): 2" in text
    assert "Source accuracy: 1/1 (100.0%)" in text
