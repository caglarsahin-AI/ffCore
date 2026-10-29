"""Acceptance tests for package 18-hazirlik (use-case scenario data, plan/18 stage 1).

Run: make test-samples   (or: py -3.12 -m unittest discover -s data/samples/scripts/tests -v)
Stdlib only. PII checks use package 08-lite's own regex recognizers
(backend/ffcore/guardrails/recognizers/regex.py, stdlib only) so "masked" and "no stray PII"
mean what the guardrail will actually see, not a second detector written here.
"""

import filecmp
import json
import random
import re
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
SAMPLES = SCRIPTS.parent
REPO = SAMPLES.parents[1]
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(REPO / "backend"))

import generate  # noqa: E402
from gen import eval as eval_gen  # noqa: E402
from gen import pii, scenarios_sql, schema  # noqa: E402

from ffcore.guardrails.recognizers.regex import recognize  # noqa: E402

SEED = 13
TICKET_CLASSES = ["access", "billing", "bug", "how_to", "other"]
CLASS_COUNTS = {"access": 5, "billing": 4, "bug": 5, "how_to": 4, "other": 2}
# Categories 08-lite's regex recognizers cover (plan/18 F2: the masked ticket must be checkable).
REGEX_CATEGORIES = {"TR_NATIONAL_ID", "TR_PHONE", "TR_IBAN", "EMAIL_ADDRESS", "CREDIT_CARD"}
# 05a SqlRejected codes (feat/05a-tools-mcp a55ca54). Checked against the real validator only
# after 05a merges (K-SEN-0002 condition 2); until then this list is the reference.
SQL_REJECT_CODES = {
    "sql_parse_error",
    "sql_multiple_statements",
    "sql_not_select",
    "sql_system_catalog",
    "sql_too_deep",
    "sql_unknown_table",
}


def _generate(out: Path, only: str) -> None:
    generate.main(["--seed", str(SEED), "--out", str(out), "--only", only])


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _fold(text: str) -> str:
    return pii.tr_lower(text)


class Test18Sql(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.items = _load(SAMPLES / "eval" / "sql-20.json")
        cls.by_id = {i["id"]: i for i in cls.items}
        cls.rows = schema.build(random.Random(f"{SEED}:schema"))

    def test_18_f3_1_sql20_shape(self):
        self.assertEqual(len(self.items), 20)
        self.assertEqual([i["id"] for i in self.items], [f"sql-{n:02d}" for n in range(1, 21)])
        for item in self.items:
            self.assertEqual(set(item), {"id", "input", "expected_output", "metadata"}, item["id"])
            self.assertEqual(set(item["input"]), {"message", "variables"})
            out = item["expected_output"]
            self.assertEqual(set(out), {"answer", "must_contain", "sql_result"}, item["id"])
            self.assertTrue(out["sql_result"], item["id"])
            self.assertTrue(out["must_contain"], item["id"])
            md = item["metadata"]
            self.assertEqual(md["tags"][0], "sql")
            self.assertTrue(md["answerable"])
            self.assertEqual(md["style"], "dogrudan")
            self.assertEqual(md["expected_docs"], [])
            self.assertTrue(md["reference_sql"].upper().startswith(("SELECT", "WITH")))
        suite = _load(SAMPLES / "eval" / "suite-sql-20.json")
        self.assertEqual(suite["key"], "sql-20")
        self.assertEqual(suite["langfuse_dataset_name"], "sql-20")
        self.assertEqual(suite["scorers"], ["sql_result", "contains"])
        self.assertEqual(suite["pass_threshold"], 0.8)

    def test_18_f3_2_reuses_13a_sql_items(self):
        base = {i["id"]: i for i in _load(SAMPLES / "eval" / "sozlesme-33.json")}
        origins = [i for i in self.items if "origin" in i["metadata"]]
        self.assertEqual(len(origins), 5)
        for item, q in zip(origins, eval_gen.SQL_QUESTIONS, strict=True):
            self.assertEqual(item["metadata"]["origin"], f"sozlesme-33/{q['id']}")
            src = base[q["id"]]
            self.assertEqual(item["input"], src["input"])
            self.assertEqual(
                item["expected_output"]["sql_result"], src["expected_output"]["sql_result"]
            )
            self.assertEqual(item["metadata"]["reference_sql"], q["sql"])

    def test_18_f3_3_expected_from_seed(self):
        questions = scenarios_sql.questions()
        self.assertEqual(len(questions), 20)
        for q in questions:
            item = self.by_id[q["id"]]
            result = scenarios_sql.result_rows(q, self.rows)
            self.assertEqual(item["expected_output"]["sql_result"], result, q["id"])
            for needle in item["expected_output"]["must_contain"]:
                self.assertIn(needle, item["expected_output"]["answer"], q["id"])
                cells = {str(c) for row in result for c in row}
                self.assertIn(needle, cells, q["id"])
        # an empty or NULL result is a generator error, never written (fail-loud)
        empty = {"id": "x", "sql": "SELECT 1", "compute": lambda rows: []}
        with self.assertRaises(ValueError):
            scenarios_sql.result_rows(empty, self.rows)
        zero = {"id": "x", "sql": "SELECT 0", "compute": lambda rows: [[0]]}
        with self.assertRaises(ValueError):
            scenarios_sql.result_rows(zero, self.rows)

    def test_18_f3_5_difficulty_mix(self):
        tags = Counter(t for i in self.items for t in i["metadata"]["tags"][1:])
        single = sum(1 for i in self.items if "join" not in i["metadata"]["tags"])
        self.assertGreaterEqual(single, 5)
        self.assertGreaterEqual(tags["join"], 5)
        self.assertGreaterEqual(tags["group"], 3)
        self.assertGreaterEqual(tags["date"], 3)
        self.assertGreaterEqual(tags["null"], 1)
        self.assertGreaterEqual(tags["multi_row"], 3)
        for i in self.items:
            rows = i["expected_output"]["sql_result"]
            self.assertEqual("multi_row" in i["metadata"]["tags"], len(rows) > 1, i["id"])

    def test_18_f3_5b_not_a_few_shot(self):
        shots = _load(SAMPLES / "schema" / "few_shots.json")
        shot_q = {_fold(s["question"]) for s in shots}
        shot_sql = {re.sub(r"\s+", " ", s["sql"]).strip().lower() for s in shots}
        for i in self.items:
            self.assertNotIn(_fold(i["input"]["message"]), shot_q, i["id"])
            sql = re.sub(r"\s+", " ", i["metadata"]["reference_sql"]).strip().lower()
            self.assertNotIn(sql, shot_sql, i["id"])

    def test_18_f3_6_write_attempts_cover_classes(self):
        attempts = _load(SAMPLES / "eval" / "sql-write-attempts.json")
        self.assertEqual(len(attempts), 12)
        self.assertEqual(len({a["id"] for a in attempts}), 12)
        for a in attempts:
            self.assertEqual(set(a), {"id", "sql", "class", "expected_code"}, a["id"])
            self.assertIn(a["expected_code"], SQL_REJECT_CODES, a["id"])
            self.assertIn(a["class"], {"write", "hidden_write", "catalog"}, a["id"])
        joined = " ".join(a["sql"].lower() for a in attempts)
        for needle in (
            "delete",
            "update ",
            "insert ",
            "drop table",
            "with ",
            "/*",
            " into ",
            "pg_",
        ):
            self.assertIn(needle, joined)
        self.assertGreaterEqual(sum(a["class"] == "hidden_write" for a in attempts), 3)


class Test18Tickets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tickets = _jsonl(SAMPLES / "tickets" / "tickets-20.jsonl")
        cls.labels = _load(SAMPLES / "tickets" / "labels.json")

    def test_18_f2_1_tickets_shape_and_labels(self):
        self.assertEqual([t["id"] for t in self.tickets], [f"tkt-{n:03d}" for n in range(1, 21)])
        for t in self.tickets:
            self.assertEqual(
                set(t), {"id", "channel", "received_at", "subject", "body", "pii"}, t["id"]
            )
            self.assertIn(t["channel"], {"email", "portal"})
            self.assertRegex(t["received_at"], r"^2025-\d{2}-\d{2}T\d{2}:\d{2}:00\+03:00$")
            self.assertTrue(t["subject"].strip() and t["body"].strip())
        self.assertEqual(self.labels["classes"], TICKET_CLASSES)
        self.assertEqual(set(self.labels["labels"]), {t["id"] for t in self.tickets})
        for tid, lab in self.labels["labels"].items():
            self.assertEqual(set(lab), {"class", "rationale"}, tid)
            self.assertIn(lab["class"], TICKET_CLASSES, tid)
            self.assertTrue(lab["rationale"].strip(), tid)
        counts = Counter(lab["class"] for lab in self.labels["labels"].values())
        self.assertEqual(dict(counts), CLASS_COUNTS)

    def test_18_f2_2_pii_spans_valid(self):
        with_pii = [t for t in self.tickets if t["pii"]]
        self.assertEqual(len(with_pii), 5)
        categories = Counter()
        for t in with_pii:
            found = {(f.start, f.end, f.category) for f in recognize(t["body"])}
            for e in t["pii"]:
                value = t["body"][e["start"] : e["end"]]
                self.assertIn(e["category"], REGEX_CATEGORIES, t["id"])
                categories[e["category"]] += 1
                if e["category"] == "TR_NATIONAL_ID":
                    self.assertTrue(pii.tc_valid(value), value)
                if e["category"] == "TR_IBAN":
                    self.assertTrue(pii.iban_valid(value.replace(" ", "")), value)
                # 08-lite finds exactly the labelled span (what F2's masking relies on)
                self.assertIn((e["start"], e["end"], e["category"]), found, (t["id"], e))
            self.assertEqual(len(found), len(t["pii"]), t["id"])
        self.assertGreaterEqual(categories["TR_NATIONAL_ID"], 2)
        self.assertGreaterEqual(categories["TR_PHONE"], 2)
        self.assertGreaterEqual(categories["EMAIL_ADDRESS"], 2)
        self.assertGreaterEqual(categories["TR_IBAN"], 1)

    def test_18_f2_3_no_stray_pii(self):
        for t in self.tickets:
            text = t["subject"] + "\n" + t["body"]
            hits = recognize(t["subject"])
            self.assertEqual(hits, [], (t["id"], "subject"))
            if not t["pii"]:
                self.assertEqual(recognize(text), [], t["id"])

    def test_18_f2_4_no_person_names(self):
        names = [_fold(n) for n in pii.FIRST_NAMES + pii.LAST_NAMES]
        patterns = [re.compile(rf"(?<!\w){re.escape(n)}(?!\w)") for n in names]
        paths = [
            SAMPLES / "tickets" / "tickets-20.jsonl",
            SAMPLES / "tickets" / "labels.json",
            SCRIPTS / "README.md",
            SAMPLES / "eval" / "sql-20.json",
            SAMPLES / "eval" / "sql-write-attempts.json",
        ]
        for path in paths:
            text = _fold(path.read_text(encoding="utf-8"))
            found = [n for n, p in zip(names, patterns, strict=True) if p.search(text)]
            self.assertEqual(found, [], path.name)

    def test_18_f2_5_labels_not_in_tickets(self):
        raw = (SAMPLES / "tickets" / "tickets-20.jsonl").read_text(encoding="utf-8")
        for word in ('"class"', '"label"', "how_to", "billing", "rationale"):
            self.assertNotIn(word, raw)


class Test18Deterministic(unittest.TestCase):
    ONLY = "scenarios_sql,tickets"
    FILES = [
        "eval/sql-20.json",
        "eval/suite-sql-20.json",
        "eval/sql-write-attempts.json",
        "tickets/tickets-20.jsonl",
        "tickets/labels.json",
    ]

    def test_18_0_deterministic(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            _generate(Path(a), self.ONLY)
            _generate(Path(b), self.ONLY)
            produced = sorted(
                p.relative_to(a).as_posix() for p in Path(a).rglob("*") if p.is_file()
            )
            self.assertEqual(produced, sorted(self.FILES))
            for rel in self.FILES:
                self.assertTrue(filecmp.cmp(Path(a) / rel, Path(b) / rel, shallow=False), rel)
                # committed data must be exactly what the generator produces
                self.assertTrue(filecmp.cmp(Path(a) / rel, SAMPLES / rel, shallow=False), rel)

    def test_18_0b_separate_rng_streams(self):
        # the new modules have their own streams: 13a modules' output does not depend on them
        self.assertIn("scenarios_sql", generate.MODULES)
        self.assertIn("tickets", generate.MODULES)
        names = list(generate.MODULES)
        self.assertEqual(
            names[: names.index("scenarios_sql")],
            ["contracts", "eval", "schema", "agents", "openapi", "pii", "memory"],
        )


if __name__ == "__main__":
    unittest.main()
