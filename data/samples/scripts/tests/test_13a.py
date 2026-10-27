"""Acceptance tests for package 13a (synthetic sample data).

Run: py -3.12 -m unittest discover -s data/samples/scripts/tests -v
Stdlib only. Each test regenerates into a temp dir and also checks that the
committed files under data/samples/ equal a fresh generation.
"""

import filecmp
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
SAMPLES = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

import generate  # noqa: E402

SEED = 13

# Fields of the agent `definition` JSON as listed in plan/06 "Agent tanımı şeması"
# and "Agent yaşam döngüsü" (prompt_ref, runtime_profile). Nothing else is allowed.
DEFINITION_FIELDS = {
    "model", "system_prompt", "langfuse_prompt", "variables", "knowledge", "tools",
    "approval", "ask_user", "guardrail_policy_key", "structured_output", "limits",
    "context_policy", "answer_rules", "reasoning", "prompt_ref", "runtime_profile",
}
SCHEMA_TABLES = {"departments", "beds", "admissions", "devices", "device_faults", "contracts_meta"}
PERSON_COLUMN = re.compile(
    r"(first_name|last_name|full_name|surname|patient|hasta|tc_|national_id|birth|"
    r"phone|email|address|person|staff|doctor|nurse)", re.IGNORECASE)


def _generate(out: Path, only: str) -> None:
    generate.main(["--seed", str(SEED), "--out", str(out), "--only", only])


def _seed_rows(seed_sql: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    table = None
    for line in seed_sql.splitlines():
        m = re.match(r"INSERT INTO (\w+) ", line)
        if m:
            table = m.group(1)
            counts.setdefault(table, 0)
        elif line.startswith("(") and table:
            counts[table] += 1
    return counts


def _schema_columns(schema_sql: str) -> dict[str, list[str]]:
    tables: dict[str, list[str]] = {}
    for name, body in re.findall(r"CREATE TABLE (\w+) \((.*?)\n\);", schema_sql, re.S):
        cols = []
        for line in body.strip().splitlines():
            word = line.strip().split()[0]
            if word.upper() not in {"PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "CONSTRAINT"}:
                cols.append(word)
        tables[name] = cols
    return tables


class Test13aSchema(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name)
        _generate(cls.out, "schema")
        cls.schema_sql = (cls.out / "schema/schema.sql").read_text(encoding="utf-8")
        cls.seed_sql = (cls.out / "schema/seed.sql").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_13a_2_schema_seed_10000_rows(self):
        self.assertEqual(set(_schema_columns(self.schema_sql)), SCHEMA_TABLES)
        counts = _seed_rows(self.seed_sql)
        self.assertEqual(set(counts), SCHEMA_TABLES)
        self.assertEqual(sum(counts.values()), 10_000, counts)

    def test_13a_2b_schema_no_person_level_columns(self):
        for table, cols in _schema_columns(self.schema_sql).items():
            for col in cols:
                self.assertIsNone(PERSON_COLUMN.search(col), f"{table}.{col}")

    def test_13a_2c_descriptions_and_20_few_shots(self):
        descs = json.loads((self.out / "schema/schema_descriptions.json").read_text(encoding="utf-8"))
        fields = {"table_name", "column_name", "description_tr", "sample_values", "is_metric", "formula"}
        described = set()
        for d in descs:
            self.assertEqual(set(d), fields)
            self.assertTrue(d["description_tr"])
            if d["is_metric"]:
                self.assertTrue(d["formula"], d)
            described.add((d["table_name"], d["column_name"]))
        for table, cols in _schema_columns(self.schema_sql).items():
            self.assertIn((table, None), described, table)
            for col in cols:
                self.assertIn((table, col), described, f"{table}.{col}")

        shots = json.loads((self.out / "schema/few_shots.json").read_text(encoding="utf-8"))
        self.assertEqual(len(shots), 20)
        self.assertEqual(len({s["question"] for s in shots}), 20)
        for s in shots:
            self.assertEqual(set(s), {"question", "sql"})
            sql = s["sql"].strip().rstrip(";")
            self.assertTrue(sql.upper().startswith(("SELECT", "WITH")), sql)
            self.assertNotIn(";", sql)
            self.assertIsNone(re.search(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|COPY|pg_\w+|information_schema)\b",
                                        sql, re.I), sql)
            # EXTRACT(x FROM col) is not a table reference
            no_extract = re.sub(r"EXTRACT\s*\([^)]*\)", "", sql, flags=re.I)
            used = set(re.findall(r"\b(?:FROM|JOIN)\s+(\w+)", no_extract, re.I))
            self.assertTrue(used and used <= SCHEMA_TABLES, (used, sql))


class Test13aAgents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        out = Path(cls.tmp.name)
        _generate(out, "agents")
        cls.agents = {p.stem: json.loads(p.read_text(encoding="utf-8"))
                      for p in sorted((out / "agents").glob("*.json"))}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_13a_3_agent_templates_match_06_fields(self):
        self.assertEqual(set(self.agents), {"sozlesme-asistani", "veri-soru-cevap", "karma-asistan"})
        for key, a in self.agents.items():
            self.assertEqual(set(a), {"key", "name", "description", "definition"}, key)
            self.assertEqual(a["key"], key)
            d = a["definition"]
            self.assertLessEqual(set(d), DEFINITION_FIELDS, key)
            self.assertNotIn("schema_version", json.dumps(a))
            self.assertEqual(d["model"], "chat-default")
            self.assertEqual(d["guardrail_policy_key"], "default")
            if "approval" in d:
                self.assertIn(d["approval"]["assign_to"], {"analyst", "developer", "admin"})

        s = self.agents["sozlesme-asistani"]["definition"]
        self.assertEqual([(k["kb_key"], k["mode"]) for k in s["knowledge"]], [("sozlesmeler", "always")])
        self.assertTrue(s["answer_rules"]["cite_sources"])
        self.assertTrue(s["answer_rules"]["unknown_reply"])
        self.assertFalse(s.get("tools"))

        # PLAN 2d decision 5 overrides brief 13 (K-13a-0002, DRIFT-25): the PoC SQL
        # assistant makes a single, approved tool call.
        v = self.agents["veri-soru-cevap"]["definition"]
        self.assertEqual(v["tools"], [{"tool_key": "mcp-sql", "actions": ["get_schema", "run_sql"]}])
        self.assertEqual(v["approval"]["actions"], ["mcp-sql.run_sql"])
        self.assertEqual(v["limits"]["max_tool_calls"], 1)
        self.assertTrue(v["ask_user"])
        self.assertFalse(v.get("knowledge"))

        k = self.agents["karma-asistan"]["definition"]
        self.assertEqual([(x["kb_key"], x["mode"]) for x in k["knowledge"]], [("sozlesmeler", "tool")])
        self.assertEqual(k["tools"][0]["tool_key"], "mcp-sql")
        self.assertIn("mcp-sql.run_sql", k["approval"]["actions"])


class Test13aOpenapi(unittest.TestCase):
    def test_13a_7_openapi_superset_6_ops(self):
        with tempfile.TemporaryDirectory() as tmp:
            _generate(Path(tmp), "openapi")
            text = (Path(tmp) / "openapi/superset.yaml").read_text(encoding="utf-8")
        self.assertTrue(text.startswith('openapi: "3.0.3"\n'))
        ops = re.findall(r"^\s+operationId: (\S+)$", text, re.M)
        self.assertEqual(len(ops), 6, ops)
        self.assertEqual(len(set(ops)), 6)
        methods = re.findall(r"^    (get|post|put|delete):$", text, re.M)
        # dashboard search, chart list, chart data, dataset metrics (get); create chart
        # (post); add chart to dashboard = update chart's dashboards (put), as in Superset.
        self.assertEqual(sorted(methods), ["get", "get", "get", "get", "post", "put"])


class Test13aDeterminism(unittest.TestCase):
    ONLY = "schema,agents,openapi"
    DIRS = ("schema", "agents", "openapi")

    def test_13a_8_deterministic(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            _generate(Path(a), self.ONLY)
            _generate(Path(b), self.ONLY)
            for sub in self.DIRS:
                self._assert_same_tree(Path(a) / sub, Path(b) / sub)
                # committed data must be exactly what the generator produces
                self._assert_same_tree(Path(a) / sub, SAMPLES / sub)

    def _assert_same_tree(self, left: Path, right: Path):
        cmp = filecmp.dircmp(left, right)
        self.assertFalse(cmp.left_only or cmp.right_only, (left, right, cmp.left_only, cmp.right_only))
        _, mismatch, errors = filecmp.cmpfiles(left, right, cmp.common_files, shallow=False)
        self.assertFalse(mismatch or errors, (right, mismatch, errors))


if __name__ == "__main__":
    unittest.main()
