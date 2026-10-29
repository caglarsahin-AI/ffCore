"""18-hazirlik data against a real, isolated Postgres loaded with the 13a demo seed.

Opt-in: set RUN_PG_TESTS=1. Reuses the 13a fixture (test_13a_pg: pinned image, unique
throwaway container, no published port, removes only its own container). Queries run as
`agent_readonly`, the role mcp-sql uses.
"""

import json
import os
import sys
import unittest
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_13a_pg as base  # noqa: E402

SAMPLES = base.SAMPLES
TABLES = ["departments", "beds", "admissions", "devices", "device_faults", "contracts_meta"]


def _same(a: str, b) -> bool:
    """Postgres text output vs the JSON value: numbers compare as decimals (4850000.00 ==
    4850000), everything else as text."""
    try:
        return Decimal(a) == Decimal(str(b))
    except InvalidOperation:
        return a == str(b)


def _snapshot() -> dict:
    """Row counts, the public tables, sequences and large objects: what a hidden write could
    change. The demo schema has no sequence (integer keys), so the sequence list is empty and
    stays empty; a write through a function shows up as a new large object."""
    sql = (
        "SELECT string_agg(table_name, ',' ORDER BY table_name) FROM "
        "information_schema.tables WHERE table_schema = 'public';\n"
        "SELECT COALESCE(string_agg(schemaname || '.' || sequencename || '=' || "
        "COALESCE(last_value::text, 'null'), ',' ORDER BY sequencename), '') FROM pg_sequences;\n"
        "SELECT COUNT(*) FROM pg_largeobject_metadata;"
    )
    tables, sequences, large_objects = base._psql(sql).stdout.split("\n")[:3]
    return {
        "counts": _counts(),
        "tables": tables,
        "sequences": sequences,
        "large_objects": int(large_objects),
    }


def _counts() -> dict[str, int]:
    out = base._psql(";\n".join(f"SELECT COUNT(*) FROM {t}" for t in TABLES) + ";").stdout
    return dict(zip(TABLES, (int(n) for n in out.split()), strict=True))


@unittest.skipUnless(
    os.environ.get("RUN_PG_TESTS") == "1", "NOT_RUN: set RUN_PG_TESTS=1 (needs Docker)"
)
class Test18Postgres(unittest.TestCase):
    # the 13a fixture's classmethods, bound to this class (no 13a tests are inherited)
    _wait_and_load = base.Test13aPostgres.__dict__["_wait_and_load"]

    @classmethod
    def setUpClass(cls):
        base.Test13aPostgres.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        base.Test13aPostgres.tearDownClass.__func__(cls)

    def test_18_f3_4_reference_sql_matches_postgres(self):
        items = json.loads((SAMPLES / "eval" / "sql-20.json").read_text(encoding="utf-8"))
        for item in items:
            sql = item["metadata"]["reference_sql"]
            out = base._psql(f"BEGIN; SET ROLE agent_readonly; {sql}; ROLLBACK;").stdout
            got = [line.split("|") for line in out.splitlines() if line]
            want = item["expected_output"]["sql_result"]
            self.assertEqual(len(got), len(want), (item["id"], got, want))
            for g, w in zip(got, want, strict=True):
                self.assertEqual(len(g), len(w), (item["id"], g, w))
                for a, b in zip(g, w, strict=True):
                    self.assertTrue(_same(a, b), (item["id"], a, b))

    def test_18_f3_7_write_attempts_fail_readonly(self):
        """Every write and hidden write fails in a session set up like mcp-sql's (05a
        mcp_sql.py: agent_readonly + default_transaction_read_only on), and nothing changes:
        row counts, tables, sequences, large objects (r1 MAJOR-1)."""
        attempts = json.loads(
            (SAMPLES / "eval" / "sql-write-attempts.json").read_text(encoding="utf-8")
        )
        before = _snapshot()
        self.assertEqual(before["tables"].split(","), sorted(TABLES))
        writes = [a for a in attempts if a["class"] in ("write", "hidden_write")]
        self.assertEqual(
            {p for a in writes for p in a["patterns"]} >= {"union", "cte", "comment", "function"},
            True,
        )
        for a in writes:
            result = base._psql(
                "SET default_transaction_read_only = on; SET ROLE agent_readonly; "
                f"BEGIN; {a['sql']}; COMMIT;",
                check=False,
            )
            self.assertNotEqual(result.returncode, 0, a["id"])
            self.assertRegex(
                result.stderr,
                r"permission denied|must be owner|read-only transaction",
                (a["id"], result.stderr),
            )
        self.assertEqual(_snapshot(), before)


if __name__ == "__main__":
    unittest.main()
