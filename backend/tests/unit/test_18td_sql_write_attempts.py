"""18-ticket-desk slice 4 (K-SEN-0002 condition 2): every record of the F3 write-attempt set
(data/samples/eval/sql-write-attempts.json, package 18) is refused by the merged 05a validator
with the code the record names, before any database connection."""

import json
from pathlib import Path

import pytest

from ffcore.services.mcp_sql import SqlRejected, validate

ATTEMPTS = json.loads(
    (
        Path(__file__).resolve().parents[3]
        / "data"
        / "samples"
        / "eval"
        / "sql-write-attempts.json"
    ).read_text(encoding="utf-8")
)
# The demo database's tables (13a schema); same set as test_05a_sql_validator.
TABLES = {"departments", "beds", "admissions", "devices", "device_faults", "contracts_meta"}


def test_18td_12_attempt_set_is_the_full_one():
    assert len(ATTEMPTS) == 15
    assert {a["class"] for a in ATTEMPTS} == {"write", "hidden_write", "catalog"}


@pytest.mark.parametrize("attempt", ATTEMPTS, ids=lambda a: a["id"])
def test_18td_12_validator_refuses_with_expected_code(attempt):
    with pytest.raises(SqlRejected) as err:
        validate(attempt["sql"], TABLES, max_rows=500)
    assert err.value.code == attempt["expected_code"], (attempt["id"], str(err.value))
