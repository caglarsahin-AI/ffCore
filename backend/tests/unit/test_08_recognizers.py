"""08-lite: regex PII recognizers measured on the 13a set (data/samples/pii, C18).

The set is produced by 13a and only read here (brief 08: this package writes no set of its own).
"""

import json
import random
import time
from pathlib import Path

import pytest

from ffcore.guardrails.categories import CATEGORIES, REGEX_CATEGORIES
from ffcore.guardrails.quality import load_set, quality_report
from ffcore.guardrails.recognizers.regex import recognize, tc_valid

REPO = Path(__file__).resolve().parents[3]
PII_SET = REPO / "data" / "samples" / "pii" / "pii-100.jsonl"
DOCS = REPO / "docs" / "guardrail.md"


@pytest.fixture(scope="module")
def records():
    return load_set(PII_SET)


@pytest.fixture(scope="module")
def report(records):
    return quality_report(records)


def test_08_1_regex_recall_tc_phone(report):
    for code in ("TR_NATIONAL_ID", "TR_PHONE"):
        row = report[code]
        assert row.support > 0, code
        assert row.recall >= 0.98, (code, row)


def test_08_1_every_regex_category_is_measured(report):
    assert set(report) == set(REGEX_CATEGORIES)
    for code, row in report.items():
        assert row.support > 0, code


def test_08_1b_quality_report_matches_docs(report):
    # docs/guardrail.md carries the measured table verbatim; a recognizer change must update it.
    from ffcore.guardrails.quality import markdown_table

    assert markdown_table(report) in DOCS.read_text(encoding="utf-8")


def test_08_7_tc_checksum():
    assert tc_valid("10000000146")
    assert not tc_valid("10000000147")  # 11th digit wrong
    assert not tc_valid("10000000156")  # 10th digit wrong
    assert not tc_valid("01234567890")  # first digit 0
    assert not tc_valid("1000000014")  # 10 digits
    assert [f.category for f in recognize("kimlik 10000000146")] == ["TR_NATIONAL_ID"]
    assert recognize("kimlik 10000000147") == []


def test_08_7_negatives_have_no_regex_findings(records):
    # 13a negatives include 11-digit numbers with an invalid TC checksum (pii-072, pii-078).
    negatives = [r for r in records if not r["entities"]]
    assert len(negatives) >= 10
    for record in negatives:
        assert recognize(record["text"]) == [], record["id"]


def test_08_1_findings_carry_evidence():
    findings = recognize("TC kimlik no 10000000146, tel 0532 256 60 38")
    assert [f.category for f in findings] == ["TR_NATIONAL_ID", "TR_PHONE"]
    tc = findings[0]
    assert tc.evidence.startswith("checksum valid")
    assert "context word" in tc.evidence
    assert (tc.start, tc.end) == (13, 24)
    assert 0 < tc.score <= 1


def test_08_1_iban_inside_text_is_not_read_as_card():
    text = "Hesap TR60 9987 5070 0891 8096 0391 33 olarak girildi."
    assert [f.category for f in recognize(text)] == ["TR_IBAN"]


def test_08_1_bare_ten_digits_are_not_a_phone():
    # A tax number (10 digits starting with 5) without prefix or separators is not a phone.
    assert recognize("vergi no 5450747061") == []
    assert [f.category for f in recognize("ara 05450747061")] == ["TR_PHONE"]
    assert [f.category for f in recognize("call +90 545 074 70 61")] == ["TR_PHONE"]


def test_08_1_category_filter():
    text = "mail a@example.com tel 0532 256 60 38"
    assert [f.category for f in recognize(text, categories={"EMAIL_ADDRESS"})] == ["EMAIL_ADDRESS"]


def test_08_2_regex_latency_p95():
    """1,000 characters, regex path only; measured and written to docs/guardrail.md."""
    from ffcore.guardrails.quality import latency_sample

    p95_ms = latency_sample(chars=1000, runs=200)
    assert p95_ms < 50, p95_ms


def test_08_21_canonical_categories(records):
    codes = {e["category"] for r in records for e in r["entities"]}
    assert codes <= set(CATEGORIES), codes - set(CATEGORIES)
    assert all(code.isascii() and code.upper() == code for code in CATEGORIES)
    md = (REPO / "data" / "samples" / "pii" / "categories.md").read_text(encoding="utf-8")
    listed = [line.split("`")[1] for line in md.splitlines() if line.startswith("| `")]
    assert listed == list(CATEGORIES)


def test_08_21_set_generator_uses_the_same_list():
    source = (REPO / "data" / "samples" / "scripts" / "gen" / "pii.py").read_text(encoding="utf-8")
    for code in CATEGORIES:
        assert f'"{code}":' in source, code


def test_08_2_latency_sample_is_deterministic_input():
    from ffcore.guardrails.quality import latency_text

    assert len(latency_text(1000)) == 1000
    assert latency_text(1000) == latency_text(1000)
    assert random.Random(0).random() == random.Random(0).random()
    assert json.dumps(latency_text(50))
    assert time.perf_counter() > 0
