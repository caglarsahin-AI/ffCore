"""Acceptance tests for package 18-hazirlik (use-case scenario data, plan/18 stage 1).

Run: make test-samples   (or: py -3.12 -m unittest discover -s data/samples/scripts/tests -v)
Stdlib only. PII checks use package 08-lite's own regex recognizers
(backend/ffcore/guardrails/recognizers/regex.py, stdlib only) so "masked" and "no stray PII"
mean what the guardrail will actually see, not a second detector written here.
"""

import base64
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
sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate  # noqa: E402
import readback  # noqa: E402
from gen import contracts, pii, scenarios_sql, schema, versions  # noqa: E402
from gen import eval as eval_gen  # noqa: E402

from ffcore.guardrails.recognizers.regex import recognize  # noqa: E402

SEED = 13
TICKET_CLASSES = ["access", "billing", "bug", "how_to", "other"]
CLASS_COUNTS = {"access": 5, "billing": 4, "bug": 5, "how_to": 4, "other": 2}
# Categories 08-lite's regex recognizers cover (plan/18 F2: the masked ticket must be checkable).
REGEX_CATEGORIES = {"TR_NATIONAL_ID", "TR_PHONE", "TR_IBAN", "EMAIL_ADDRESS", "CREDIT_CARD"}
# 05a SqlRejected codes (feat/05a-tools-mcp a55ca54). Checked against the real validator only
# after 05a merges (K-SEN-0002 condition 2); until then this list is the reference.
# How a write is hidden (sql-write-attempts.json `patterns`) and the text that proves it.
WRITE_PATTERNS = {
    "union": r"(?i)\bunion\b",
    "cte": r"(?i)^\s*with\b",
    "comment": r"/\*|--",
    "function": r"(?i)\b(lo_create|lo_import|setval|nextval)\s*\(",
    "second_statement": r";\s*\S",
    "select_into": r"(?i)\bselect\b[^;]*\binto\b",
}
# A statement that would change data or schema if it ran.
WRITE_EFFECT = (
    r"(?i)\b(delete|update|insert|drop|truncate|alter|into|lo_create|lo_import|setval|nextval)\b"
)
SQL_REJECT_CODES = {
    "sql_parse_error",
    "sql_multiple_statements",
    "sql_not_select",
    "sql_system_catalog",
    "sql_function_not_allowed",
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
        self.assertEqual(len({a["id"] for a in attempts}), len(attempts))
        for a in attempts:
            self.assertEqual(set(a), {"id", "sql", "class", "expected_code", "patterns"}, a["id"])
            self.assertIn(a["expected_code"], SQL_REJECT_CODES, a["id"])
            self.assertIn(a["class"], {"write", "hidden_write", "catalog"}, a["id"])
            self.assertTrue(set(a["patterns"]) <= set(WRITE_PATTERNS), a["id"])
            # every declared pattern is really in the statement
            for pattern in a["patterns"]:
                self.assertRegex(a["sql"], WRITE_PATTERNS[pattern], (a["id"], pattern))
            # a hidden write must actually try to write (review r1 MAJOR-1)
            if a["class"] == "hidden_write":
                self.assertRegex(a["sql"], WRITE_EFFECT, a["id"])
        joined = " ".join(a["sql"].lower() for a in attempts)
        for needle in ("delete", "update ", "insert ", "drop table", "truncate", "alter "):
            self.assertIn(needle, joined)

    def test_18_f3_6b_hidden_write_pattern_coverage(self):
        """Each way of hiding a write has at least one hidden_write record (r1 MAJOR-1:
        the UNION case had been a catalog read)."""
        attempts = _load(SAMPLES / "eval" / "sql-write-attempts.json")
        hidden = [a for a in attempts if a["class"] == "hidden_write"]
        covered = {p for a in hidden for p in a["patterns"]}
        for pattern in ("union", "cte", "comment", "function", "second_statement", "select_into"):
            self.assertIn(pattern, covered, pattern)


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


class Test18Poison(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.expected = _load(SAMPLES / "poison" / "expected.json")
        cls.tickets = _jsonl(SAMPLES / "poison" / "tickets-poison.jsonl")
        cls.docs = {
            d["id"]: (SAMPLES / d["file"]).read_text(encoding="utf-8")
            for d in cls.expected["documents"]
        }

    def test_18_f11_1_shape(self):
        docs, tkts = self.expected["documents"], self.expected["tickets"]
        self.assertEqual(len(docs), 5)
        self.assertEqual(len(tkts), 3)
        self.assertEqual(
            {d["kind"] for d in docs},
            {"ignore_rules", "hidden_tool_call", "exfiltration", "role_change", "encoded"},
        )
        self.assertEqual([t["id"] for t in self.tickets], [t["id"] for t in tkts])
        for t in self.tickets:
            self.assertEqual(
                set(t), {"id", "channel", "received_at", "subject", "body", "pii"}, t["id"]
            )
            self.assertEqual(t["pii"], [])
        for t in tkts:
            self.assertIn(t["expected_class"], TICKET_CLASSES)
            self.assertTrue(
                t["must_not_contain"] or t["forbidden_tools"] or t["forbidden_tool_calls"]
            )
        for d in docs:
            self.assertTrue(d["file"].endswith(".txt"), d["id"])  # 04a plaintext path
            self.assertTrue(d["must_not_contain"] or d["forbidden_tools"], d["id"])
            self.assertIn(d["injection"], self.docs[d["id"]])

    def test_18_f11_2_canaries_only_in_injection(self):
        corpus = "\n".join(self.docs.values())
        for d in self.expected["documents"]:
            for needle in d["must_not_contain"]:
                if needle.startswith(("KANARYA-", "SIZINTI-")):
                    expected = 0 if d["kind"] == "encoded" else 1
                    self.assertEqual(corpus.count(needle), expected, needle)
                    if expected:
                        self.assertIn(needle, d["injection"])
                for fact in d["must_contain"]:
                    self.assertNotIn(needle, fact)
        # the encoded canary is only readable after decoding the injection line
        p5 = next(d for d in self.expected["documents"] if d["kind"] == "encoded")
        payload = p5["injection"].rsplit(" ", 1)[1]
        self.assertIn("KANARYA-B64X", base64.b64decode(payload).decode("utf-8"))

    def test_18_f11_3_legit_fact_present(self):
        for d in self.expected["documents"]:
            text = self.docs[d["id"]].replace(d["injection"], "")
            for fact in d["must_contain"]:
                self.assertIn(fact, text, d["id"])

    def test_18_f11_4_no_pii_no_names(self):
        names = [_fold(n) for n in pii.FIRST_NAMES + pii.LAST_NAMES]
        patterns = [re.compile(rf"(?<!\w){re.escape(n)}(?!\w)") for n in names]
        texts = list(self.docs.values())
        texts += [t["subject"] + "\n" + t["body"] for t in self.tickets]
        for text in texts:
            self.assertEqual(recognize(text), [], text[:40])
            found = [n for n, p in zip(names, patterns, strict=True) if p.search(_fold(text))]
            self.assertEqual(found, [], text[:40])

    def test_18_f11_5_b2_target_value(self):
        b2 = next(t for t in self.expected["tickets"] if t["kind"] == "cross_ticket_leak")
        src = next(
            t for t in _jsonl(SAMPLES / "tickets" / "tickets-20.jsonl") if t["id"] == "tkt-002"
        )
        ids = [
            src["body"][e["start"] : e["end"]]
            for e in src["pii"]
            if e["category"] == "TR_NATIONAL_ID"
        ]
        self.assertEqual(b2["must_not_contain"], ids)
        self.assertTrue(pii.tc_valid(ids[0]))
        self.assertEqual(
            b2["forbidden_tool_calls"], [{"tool": "get_ticket", "ticket_id": "tkt-002"}]
        )


class Test18Projects(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = _load(SAMPLES / "projects" / "projects.json")

    def test_18_f10_1_projects_shape(self):
        key_pattern = re.compile(r"^[a-z][a-z0-9-]{1,31}$")  # 03a PROJECT_KEY_PATTERN
        ps = self.doc["projects"]
        self.assertEqual(len(ps), 2)
        emails = []
        for p in ps:
            self.assertRegex(p["key"], key_pattern)
            kinds = {(m["role"], m["access"]) for m in p["members"]}
            self.assertEqual(kinds, {("admin", "edit"), ("admin", "read"), ("analyst", "edit")})
            emails += [m["email"] for m in p["members"]]
            for m in p["members"]:
                self.assertTrue(m["email"].endswith("@example.test"), m["email"])
        self.assertEqual(len(emails), len(set(emails)))
        iso = self.doc["isolation"]
        self.assertEqual({iso["viewer_project"], iso["target_project"]}, {p["key"] for p in ps})
        self.assertEqual(iso["expected_status"], 404)

    def test_18_f10_2_no_secret(self):
        raw = (SAMPLES / "projects" / "projects.json").read_text(encoding="utf-8").lower()
        for word in ("password", "parola", "sifre", "şifre", "token", "secret"):
            self.assertNotIn(word, raw)

    def test_18_f10_3_sources_exist(self):
        for p in self.doc["projects"]:
            for kb in p["knowledge_bases"]:
                src = SAMPLES / kb["source"]
                self.assertTrue(src.is_dir() and any(src.iterdir()), kb)
            for agent in p["agents"]:
                self.assertTrue((SAMPLES / "agents" / f"{agent}.json").is_file(), agent)


class Test18Versions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.expected = _load(SAMPLES / "versions" / "expected.json")
        cls.built = {v["contract"]["code"]: v for v in versions.build(SEED)}

    def test_18_f13_1_replay_v1_identical(self):
        self.assertEqual(len(self.expected), 2)
        for e in self.expected:
            v1_file = (SAMPLES / e["v1_file"]).read_bytes()
            self.assertEqual(self.built[e["code"]]["v1_bytes"], v1_file, e["code"])

    def test_18_f13_2_single_clause_changed(self):
        for e in self.expected:
            v = self.built[e["code"]]
            old, new = v["v1_blocks"], v["v2_blocks"]
            self.assertEqual(len(new), len(old) + 1)  # + the version note
            note = new[2][1]
            self.assertIn("Sürüm 2", note)
            self.assertIn(e["changed_clause"], note)
            self.assertIn("01.09.2025", note)
            rest = new[:2] + new[3:]
            diff = [(a, b) for a, b in zip(old, rest, strict=True) if a != b]
            self.assertEqual(len(diff), 1, e["code"])
            (_, before), (_, after) = diff[0]
            self.assertTrue(before.startswith(e["changed_clause"] + " "), before)
            self.assertIn(e["v1_value"], before)
            self.assertIn(e["v2_value"], after)
            self.assertNotIn(e["v2_value"], before)
            # the file on disk carries the new value and not the old one
            v2_text = readback.text_of(SAMPLES / e["v2_file"])
            self.assertIn(e["v2_value"], v2_text)
            self.assertNotIn(e["v1_value"], v2_text)

    def test_18_f13_3_not_in_f1_exam(self):
        exam = _load(SAMPLES / "eval" / "sozlesme-33.json")
        needles = [x for e in self.expected for x in (e["v1_value"], e["v2_value"])]
        for item in exam:
            out = item["expected_output"]
            text = " ".join([out.get("answer", "")] + out.get("must_contain", []))
            for n in needles:
                self.assertNotIn(n, text, item["id"])
        codes = {c["code"] for c in contracts.CONTRACTS}
        self.assertTrue({e["code"] for e in self.expected} <= codes)


class Test18Agents(unittest.TestCase):
    """The two scenario agents (18-ticket-desk, K-SEN-0011): same shape as the 13a templates;
    06a's schema check is the lasting gate once 06a is merged (K-SEN-0012)."""

    KEYS = ("zehirli-belge-asistani", "surum-asistani")

    @classmethod
    def setUpClass(cls):
        cls.agents = {k: _load(SAMPLES / "agents" / f"{k}.json") for k in cls.KEYS}
        cls.reference = _load(SAMPLES / "agents" / "karma-asistan.json")["definition"]

    def test_18_ag_1_same_shape_as_13a_templates(self):
        for key, agent in self.agents.items():
            self.assertEqual(set(agent), {"key", "name", "description", "definition"}, key)
            self.assertEqual(agent["key"], key)
            d = agent["definition"]
            shape = set(self.reference) - ({"approval"} if not d["tools"] else set())
            self.assertEqual(set(d), shape, key)
            self.assertEqual(d["model"], "chat-default", key)
            self.assertEqual(d["guardrail_policy_key"], "default", key)

    def test_18_ag_2_poison_agent_has_its_kb_and_a_tool_to_resist(self):
        d = self.agents["zehirli-belge-asistani"]["definition"]
        self.assertEqual([k["kb_key"] for k in d["knowledge"]], ["zehirli"])
        self.assertEqual(d["knowledge"][0]["mode"], "always")
        # P2/tkt-p03 forbid run_sql: the agent has it, so the refusal is the model's, not absent
        forbidden = {
            t
            for doc in _load(SAMPLES / "poison" / "expected.json")["documents"]
            for t in doc["forbidden_tools"]
        }
        actions = {a for t in d["tools"] for a in t["actions"]}
        self.assertTrue(forbidden, "no forbidden tool in poison/expected.json")
        self.assertTrue(forbidden <= actions, (forbidden, actions))
        # a tool call it is lured into still waits for a person
        self.assertEqual(
            set(d["approval"]["actions"]),
            {f"{t['tool_key']}.{a}" for t in d["tools"] for a in t["actions"]},
        )
        self.assertTrue(d["answer_rules"]["cite_sources"])
        self.assertIn("talimat", d["system_prompt"])

    def test_18_ag_3_version_agent_reads_versions_kb_and_names_the_date(self):
        d = self.agents["surum-asistani"]["definition"]
        self.assertEqual([k["kb_key"] for k in d["knowledge"]], ["surumler"])
        self.assertEqual(d["tools"], [])
        self.assertNotIn("approval", d)
        self.assertTrue(d["answer_rules"]["cite_sources"])
        for needle in ("yürürlük", "önceki"):
            self.assertIn(needle, d["system_prompt"])


class Test18Deterministic(unittest.TestCase):
    ONLY = "scenarios_sql,tickets,poison,projects,versions"
    FILES = [
        "eval/sql-20.json",
        "eval/suite-sql-20.json",
        "eval/sql-write-attempts.json",
        "tickets/tickets-20.jsonl",
        "tickets/labels.json",
        "poison/docs/p1-cihaz-teslim-tesellum.txt",
        "poison/docs/p2-ariza-bildirim-yonergesi.txt",
        "poison/docs/p3-bilgi-guvenligi-talimati.txt",
        "poison/docs/p4-sterilizasyon-calisma-esaslari.txt",
        "poison/docs/p5-tibbi-atik-proseduru.txt",
        "poison/tickets-poison.jsonl",
        "poison/expected.json",
        "projects/projects.json",
        "projects/klinik-b/b-el-hijyeni-proseduru.txt",
        "versions/SZL-2025-003_temizlik-hizmet_v2.docx",
        "versions/SZL-2025-007_laboratuvar-kiti_v2.docx",
        "versions/expected.json",
        "agents/zehirli-belge-asistani.json",
        "agents/surum-asistani.json",
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
        for name in ("tickets", "poison", "projects", "versions"):
            self.assertIn(name, generate.MODULES)
        names = list(generate.MODULES)
        self.assertEqual(
            names[: names.index("scenarios_sql")],
            ["contracts", "eval", "schema", "agents", "openapi", "pii", "memory"],
        )


if __name__ == "__main__":
    unittest.main()
