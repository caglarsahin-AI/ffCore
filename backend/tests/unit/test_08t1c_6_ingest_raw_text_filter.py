"""08 tam 1c, FOLLOWUP-174: `ingest-raw --text-filter pii_regex` is the explicit identifier-only
filter for sources without person data, apart from the M3 flag.

Without NER weights (an empty `NER_MODEL`) a non-PRSIM source stopped with `ner_unavailable`, and
the only way through was `--accept-personnel-data`, whose name says the opposite. PRSIM still
needs NER (or the M3 flag); the default stays `pii_ner`; masking cannot be named away.
"""

import pytest

from ffcore import cli
from ffcore.knowledge import raw_ingest


@pytest.fixture
def calls(monkeypatch):
    seen = []

    async def fake_tree(**kwargs):
        seen.append(kwargs)
        return raw_ingest.RawIngestReport(text_filter=kwargs["text_filter"])

    async def no_ner(sources):
        raise AssertionError("pii_regex asked the NER")

    monkeypatch.setattr(raw_ingest, "ingest_tree", fake_tree)
    monkeypatch.setattr(raw_ingest, "check_ner", no_ner)
    return seen


def _ingest(tmp_path, *extra, sources=("confluence:OCR",)):
    raw = tmp_path / "raw"
    raw.mkdir(exist_ok=True)
    return cli.main(
        [
            "ingest-raw",
            "--project",
            "p",
            "--kb",
            "k",
            "--raw-dir",
            str(raw),
            "--acl",
            "analyst",
            "--sources",
            *sources,
            *extra,
        ]
    )


def test_08t1c_6_text_filter_pii_regex_without_m3_flag(calls, tmp_path):
    assert _ingest(tmp_path, "--text-filter", "pii_regex") == 0
    ((kwargs,),) = [calls]
    assert kwargs["text_filter"] == "pii_regex"
    assert kwargs["accept_personnel_data"] is False


def test_08t1c_6b_pii_regex_still_refuses_prsim(calls, tmp_path, capsys):
    assert _ingest(tmp_path, "--text-filter", "pii_regex", sources=("jira:PRSIM",)) == 2
    assert "prsim_requires_ner" in capsys.readouterr().err
    assert calls == []


def test_08t1c_6c_default_stays_pii_ner(calls, tmp_path):
    # (ingest_tree checks the NER itself for non-PRSIM sources; faked here)
    assert _ingest(tmp_path) == 0
    assert calls[0]["text_filter"] == "pii_ner"


def test_08t1c_6d_m3_flag_with_pii_ner_is_a_conflict(calls, tmp_path, capsys):
    flags = ("--accept-personnel-data", "--text-filter", "pii_ner")
    assert _ingest(tmp_path, *flags) == 2
    assert "text_filter_conflict" in capsys.readouterr().err
    assert calls == []


def test_08t1c_6e_no_filter_choice_turns_masking_off(tmp_path, capsys):
    with pytest.raises(SystemExit) as exit_:
        _ingest(tmp_path, "--text-filter", "none")
    assert exit_.value.code == 2
