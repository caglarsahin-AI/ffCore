"""13a demo schema against a real, isolated Postgres (acceptance 2d, 4d groundwork).

Opt-in: set RUN_PG_TESTS=1. Uses the image pinned by package 00
(pgvector/pgvector:0.8.1-pg16), a throwaway container named ffcore-13a-pg with no
published ports and trust auth inside the container only (no secret), removed after.
Approved by the coordinator in K-13a-0002.
"""

import os
import random
import subprocess
import sys
import time
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
SAMPLES = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

from gen import schema  # noqa: E402

IMAGE = "pgvector/pgvector:0.8.1-pg16"
CONTAINER = "ffcore-13a-pg"
SEED = 13


def _docker(*args: str, stdin: str | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], input=stdin, capture_output=True, text=True,
                          encoding="utf-8", check=check)


def _psql(sql: str, check: bool = True) -> subprocess.CompletedProcess:
    return _docker("exec", "-i", CONTAINER, "psql", "-U", "postgres", "-v", "ON_ERROR_STOP=1",
                   "-qAt", "-f", "-", stdin=sql, check=check)


@unittest.skipUnless(os.environ.get("RUN_PG_TESTS") == "1", "NOT_RUN: set RUN_PG_TESTS=1 (needs Docker)")
class Test13aPostgres(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _docker("rm", "-f", CONTAINER, check=False)
        _docker("run", "-d", "--rm", "--name", CONTAINER, "-e", "POSTGRES_HOST_AUTH_METHOD=trust", IMAGE)
        deadline = time.monotonic() + 60
        while _docker("exec", CONTAINER, "pg_isready", "-U", "postgres", check=False).returncode != 0:
            if time.monotonic() > deadline:
                raise RuntimeError("postgres did not become ready in 60 s")
            time.sleep(1)
        # The entrypoint restarts the server once after init; wait until queries work.
        while _psql("SELECT 1;", check=False).returncode != 0:
            if time.monotonic() > deadline:
                raise RuntimeError("postgres did not accept queries in 60 s")
            time.sleep(1)
        for name in ("schema.sql", "seed.sql", "readonly_role.sql"):
            _psql((SAMPLES / "schema" / name).read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        _docker("rm", "-f", CONTAINER, check=False)

    def test_13a_2d_postgres_load(self):
        expected = schema.build(random.Random(f"{SEED}:schema"))
        for table, rows in expected.items():
            got = int(_psql(f"SELECT COUNT(*) FROM {table};").stdout.strip())
            self.assertEqual(got, len(rows), table)

    def test_13a_4d_sql_expected_results_in_postgres(self):
        import json
        from gen import eval as eval_gen
        items = {i["id"]: i for i in json.loads((SAMPLES / "eval" / "sozlesme-33.json").read_text(encoding="utf-8"))}
        for q in eval_gen.SQL_QUESTIONS:
            got = _psql(f"BEGIN; SET ROLE agent_readonly; {q['sql']}; ROLLBACK;").stdout.split()
            self.assertEqual([[int(got[0])]], items[q["id"]]["expected_output"]["sql_result"], q["id"])

    def test_13a_2e_few_shots_run_as_readonly(self):
        import json
        shots = json.loads((SAMPLES / "schema" / "few_shots.json").read_text(encoding="utf-8"))
        for s in shots:
            result = _psql(f"BEGIN; SET ROLE agent_readonly; {s['sql']}; ROLLBACK;", check=False)
            self.assertEqual(result.returncode, 0, (s["question"], result.stderr))
        denied = _psql("BEGIN; SET ROLE agent_readonly; DELETE FROM device_faults; ROLLBACK;", check=False)
        self.assertNotEqual(denied.returncode, 0)
        self.assertIn("permission denied", denied.stderr)


if __name__ == "__main__":
    unittest.main()
