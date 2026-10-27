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
import random  # noqa: E402

from gen import contracts, pdf, schema  # noqa: E402
from gen import eval as eval_gen  # noqa: E402
from gen.words import CONTRACTS  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import readback  # noqa: E402

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


class Test13aContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "contracts"
        _generate(Path(cls.tmp.name), "contracts")
        cls.manifest = json.loads((cls.out / "manifest.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_13a_1_contracts_count_and_formats(self):
        self.assertGreaterEqual(len(self.manifest), 5)
        files = sorted(p.name for p in self.out.iterdir() if p.name != "manifest.json")
        self.assertEqual(files, sorted(m["file_name"] for m in self.manifest))
        formats = {m["format"] for m in self.manifest}
        self.assertEqual(formats, {"pdf", "docx"})
        for m in self.manifest:
            data = (self.out / m["file_name"]).read_bytes()
            self.assertTrue(data.startswith(b"%PDF-" if m["format"] == "pdf" else b"PK\x03\x04"), m)
            if m["format"] == "pdf":
                self.assertEqual(len(readback.pdf_info(data)["pages"]), m["pages"], m["file_name"])
        acls = [m["acl_roles"] for m in self.manifest]
        self.assertIn(["admin"], acls)      # 04 ACL test: admin-only document
        self.assertIn([], acls)             # C15: empty ACL = all project members
        self.assertIn(10, [m["pages"] for m in self.manifest])  # 04: 10-page ingest timing

    def test_13a_1b_contracts_structure(self):
        for c in CONTRACTS:
            path = self.out / c["file_name"]
            text = " ".join(readback.text_of(path).split())  # PDF lines wrap mid-phrase
            self.assertIn("Madde 10 - Fesih", text, path.name)
            self.assertIn(f"en az {c['notice_days']} gün önceden", text, path.name)
            self.assertIn(c["vendor"], text)
            # Turkish letters survive the round trip: ş ğ ı İ ü ö ç Ş all occur in fixed clause text
            for phrase in ("Kişisel Verilerin Korunması Kanunu", "Doğal afet", "kalkıncaya",
                           "İdarenin bulunduğu yer", "çözümü", "Yüklenicinin yükümlülükleri", "Ş"):
                self.assertIn(phrase, text, (path.name, phrase))
            data = path.read_bytes()
            if c["format"] == "pdf":
                info = readback.pdf_info(data)
                self.assertTrue(info["flate"])
                self.assertIn(b"/ToUnicode", info["font"])
                self.assertIn(b"/Differences", data)
                # Clause text must come back exactly; the trailing annex rows (header + 8)
                # are seeded and the page footers are not body text.
                expected = [line for _, line in pdf.layout(contracts.blocks(c, random.Random(0))) if line]
                got = [line for page in info["pages"] for line in page if not line.startswith("Sayfa ")]
                body = len(expected) - 9
                self.assertEqual(got[:body], expected[:body])
            else:
                info = readback.docx_info(data)
                styles = {s for s, _ in info["paragraphs"]}
                self.assertTrue({"Heading1", "Heading2"} <= styles)
                self.assertGreaterEqual(info["tables"], 2)


def _fold(s: str) -> str:
    return " ".join(s.replace("İ", "i").replace("I", "ı").lower().split())


class Test13aEval(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        out = Path(cls.tmp.name)
        _generate(out, "contracts,eval")
        cls.items = json.loads((out / "eval/sozlesme-33.json").read_text(encoding="utf-8"))
        cls.suite = json.loads((out / "eval/suite.json").read_text(encoding="utf-8"))
        manifest = json.loads((out / "contracts/manifest.json").read_text(encoding="utf-8"))
        cls.acl = {m["file_name"]: m["acl_roles"] for m in manifest}
        cls.texts = {m["file_name"]: _fold(readback.text_of(out / "contracts" / m["file_name"])) for m in manifest}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_13a_4_eval_distribution(self):
        # The briefs' "35" label was an arithmetic slip: the mandated split 12+8+5+3+5
        # is 33 (K-13a-0003, DRIFT-28).
        self.assertEqual(len(self.items), 33)
        self.assertEqual(len(self.items), 12 + 8 + 5 + 3 + 5)
        self.assertEqual(len({i["id"] for i in self.items}), len(self.items))
        sql = [i for i in self.items if "sql" in i["metadata"]["tags"]]
        self.assertEqual(len(sql), 5)
        styles = {}
        for i in self.items:
            if i not in sql:
                styles[i["metadata"]["style"]] = styles.get(i["metadata"]["style"], 0) + 1
        self.assertEqual(styles, {"dogrudan": 12, "dolayli": 8, "alan_ici_cevapsiz": 5, "alan_disi_cevapsiz": 3})
        self.assertEqual(self.suite["scorers"], ["contains", "cites_source", "sql_result", "llm_judge"])
        self.assertEqual(self.suite["pass_threshold"], 0.8)
        self.assertEqual(self.suite["langfuse_dataset_name"], "sozlesme-33")

    def test_13a_4b_eval_required_metadata(self):
        styles = {"dogrudan", "dolayli", "alan_ici_cevapsiz", "alan_disi_cevapsiz"}
        for i in self.items:
            self.assertEqual(set(i), {"id", "input", "expected_output", "metadata"}, i["id"])
            self.assertEqual(set(i["input"]), {"message", "variables"})
            md = i["metadata"]
            self.assertEqual(set(md), {"tags", "answerable", "style", "expected_docs"}, i["id"])
            self.assertIn(md["style"], styles)
            eo = i["expected_output"]
            self.assertLessEqual(set(eo), {"answer", "must_contain", "must_cite", "sql_result", "json"})
            if "sql" in md["tags"]:
                self.assertTrue(md["answerable"])
                self.assertEqual(md["expected_docs"], [])
                self.assertIsInstance(eo["sql_result"], list)
            elif md["style"].endswith("cevapsiz"):
                self.assertFalse(md["answerable"], i["id"])
                self.assertEqual(md["expected_docs"], [])
                self.assertNotIn("must_cite", eo)
            else:
                self.assertTrue(md["answerable"])
                self.assertTrue(md["expected_docs"])
                self.assertEqual(eo["must_cite"], md["expected_docs"])
                for doc in md["expected_docs"]:
                    self.assertIn(doc, self.acl)
                    self.assertNotEqual(self.acl[doc], ["admin"], (i["id"], "eval runs as analyst"))
                    for phrase in eo["must_contain"]:
                        self.assertIn(_fold(phrase), self.texts[doc], (i["id"], phrase))

    def test_13a_4c_eval_answerability_checks(self):
        by_id = {i["id"]: i for i in self.items}
        for q in eval_gen.QUESTIONS:
            item = by_id[q["id"]]
            if q["style"].endswith("cevapsiz"):
                for term in q["absent_terms"]:   # 0 hits in the whole KB
                    for doc, text in self.texts.items():
                        self.assertNotIn(_fold(term), text, (q["id"], term, doc))
            if q["style"] == "dolayli":
                term = _fold(q["avoided_term"])  # in the document, not in the question
                self.assertNotIn(term, _fold(item["input"]["message"]), q["id"])
                self.assertIn(term, self.texts[q["doc"]], q["id"])

    def test_13a_4d_sql_expected_results(self):
        rows = schema.build(random.Random(f"{SEED}:schema"))
        by_id = {i["id"]: i for i in self.items}
        for q in eval_gen.SQL_QUESTIONS:
            self.assertEqual(by_id[q["id"]]["expected_output"]["sql_result"], [[q["compute"](rows)]], q["id"])
            self.assertGreater(q["compute"](rows), 0, q["id"])  # a zero would not discriminate


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
    ONLY = "contracts,schema,agents,eval,openapi"
    DIRS = ("contracts", "schema", "agents", "eval", "openapi")

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
