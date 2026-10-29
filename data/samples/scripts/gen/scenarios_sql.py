"""F3 data (plan/18): the 20-question SQL exam `sql-20.json` and the write attempts its
negative test feeds to mcp-sql.

The first five questions are 13a's (eval.SQL_QUESTIONS, imported, not copied); fifteen are new.
Every expected result is computed from schema.build(), the same rows seed.sql is written from,
and test_18_pg runs each reference SQL as agent_readonly against that seed. Nothing is typed in
by hand. None of the questions repeats a few-shot (schema.FEW_SHOTS), or the exam would measure
the prompt's examples.

Item shape is 13a's (plan/09 Langfuse mapping); metadata adds `reference_sql`, the feature
tags after "sql" (join, group, date, null, multi_row) and, for the reused five, `origin`.
"""

import json
import random
from decimal import Decimal
from pathlib import Path

from . import eval as eval_set
from . import schema, write_text

YBAK, PEDI, KARD = "YBAK", "PEDI", "KARD"
ORIGIN_TAGS = {
    "q29": [],
    "q30": ["join", "date"],
    "q31": [],
    "q32": [],
    "q33": ["null"],
}


def _dep(rows, code: str) -> tuple:
    return next(r for r in rows["departments"] if r[1] == code)


def _device_dep(rows) -> dict[int, int]:
    return {r[0]: r[1] for r in rows["devices"]}


def _dec(value) -> Decimal:
    return Decimal(repr(value)) if isinstance(value, float) else Decimal(value)


def _ranked(counts: dict, limit: int | None = None) -> list[list]:
    """ORDER BY count DESC, key ASC (the reference SQL orders the same way)."""
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [[k, v] for k, v in ordered[:limit]]


def _vendor_active(rows):
    counts: dict[str, int] = {}
    for r in rows["devices"]:
        if r[6] == "aktif":
            counts[r[4]] = counts.get(r[4], 0) + 1
    return _ranked(counts)


def _fault_types(rows):
    counts: dict[str, int] = {}
    for r in rows["device_faults"]:
        counts[r[3]] = counts.get(r[3], 0) + 1
    return _ranked(counts)


def _ybak_downtime(rows):
    dep_of = _device_dep(rows)
    ybak = _dep(rows, YBAK)[0]
    return [[sum((_dec(f[6]) for f in rows["device_faults"] if dep_of[f[1]] == ybak), Decimal())]]


def _top_downtime_department(rows):
    dep_of = _device_dep(rows)
    names = {r[0]: r[2] for r in rows["departments"]}
    totals: dict[str, Decimal] = {}
    for f in rows["device_faults"]:
        if "2025-01-01" <= f[2] <= "2025-12-31":
            name = names[dep_of[f[1]]]
            totals[name] = totals.get(name, Decimal()) + _dec(f[6])
    ordered = sorted(totals.items(), key=lambda kv: -kv[1])
    if ordered[0][1] == ordered[1][1]:
        raise ValueError("top downtime department is tied; LIMIT 1 would be ambiguous")
    return [list(ordered[0])]


NEW_QUESTIONS = [
    {
        "q": "Kardiyoloji bölümü kaçıncı katta?",
        "sql": "SELECT floor FROM departments WHERE code = 'KARD'",
        "tags": [],
        "compute": lambda rows: [[_dep(rows, KARD)[3]]],
    },
    {
        "q": "Dahiliye bölümünde kullanımda olan kaç yatak var?",
        "sql": "SELECT COUNT(*) FROM beds b JOIN departments d ON d.id = b.department_id "
        "WHERE d.code = 'DAHI' AND b.is_active = TRUE",
        "tags": ["join"],
        "compute": lambda rows: [
            [sum(1 for b in rows["beds"] if b[1] == _dep(rows, "DAHI")[0] and b[4])]
        ],
    },
    {
        "q": "Bakımda olan kaç ventilatör var?",
        "sql": "SELECT COUNT(*) FROM devices "
        "WHERE device_type = 'ventilator' AND status = 'bakimda'",
        "tags": [],
        "compute": lambda rows: [
            [sum(1 for r in rows["devices"] if r[3] == "ventilator" and r[6] == "bakimda")]
        ],
    },
    {
        "q": "En eski infüzyon pompası hangi tarihte kurulmuş?",
        "sql": "SELECT MIN(installed_on) FROM devices WHERE device_type = 'infuzyon_pompasi'",
        "tags": ["date"],
        "compute": lambda rows: [
            [min(r[5] for r in rows["devices"] if r[3] == "infuzyon_pompasi")]
        ],
    },
    {
        "q": "Üreticilere göre aktif durumdaki cihaz sayıları nedir?",
        "sql": "SELECT vendor, COUNT(*) AS adet FROM devices WHERE status = 'aktif' "
        "GROUP BY vendor ORDER BY adet DESC, vendor",
        "tags": ["group", "multi_row"],
        "compute": _vendor_active,
    },
    {
        "q": "Kritik önemdeki arızalardan kaçı hâlâ açık?",
        "sql": "SELECT COUNT(*) FROM device_faults "
        "WHERE severity = 'kritik' AND resolved_on IS NULL",
        "tags": ["null"],
        "compute": lambda rows: [
            [sum(1 for r in rows["device_faults"] if r[4] == "kritik" and r[5] is None)]
        ],
    },
    {
        "q": "Haziran 2025'te kaç arıza bildirildi?",
        "sql": "SELECT COUNT(*) FROM device_faults "
        "WHERE reported_on BETWEEN '2025-06-01' AND '2025-06-30'",
        "tags": ["date"],
        "compute": lambda rows: [
            [sum(1 for r in rows["device_faults"] if "2025-06-01" <= r[2] <= "2025-06-30")]
        ],
    },
    {
        "q": "Yoğun Bakım bölümündeki cihazların toplam arıza kesintisi kaç saat?",
        "sql": "SELECT SUM(f.downtime_hours) FROM device_faults f JOIN devices v ON v.id = "
        "f.device_id JOIN departments d ON d.id = v.department_id WHERE d.code = 'YBAK'",
        "tags": ["join"],
        "compute": _ybak_downtime,
    },
    {
        "q": "Her arıza türünden kaç kayıt var?",
        "sql": "SELECT fault_type, COUNT(*) AS adet FROM device_faults "
        "GROUP BY fault_type ORDER BY adet DESC, fault_type",
        "tags": ["group", "multi_row"],
        "compute": _fault_types,
    },
    {
        "q": "2026'nın ilk yarısında sona erecek kaç sözleşme var?",
        "sql": "SELECT COUNT(*) FROM contracts_meta "
        "WHERE end_date BETWEEN '2026-01-01' AND '2026-06-30'",
        "tags": ["date"],
        "compute": lambda rows: [
            [sum(1 for r in rows["contracts_meta"] if "2026-01-01" <= r[6] <= "2026-06-30")]
        ],
    },
    {
        "q": "Fesih bildirim süresi en az 60 gün olan sözleşmeler ve süreleri nedir?",
        "sql": "SELECT contract_code, notice_days FROM contracts_meta WHERE notice_days >= 60 "
        "ORDER BY notice_days DESC, contract_code",
        "tags": ["multi_row"],
        "compute": lambda rows: [
            [r[1], r[8]]
            for r in sorted(rows["contracts_meta"], key=lambda r: (-r[8], r[1]))
            if r[8] >= 60
        ],
    },
    {
        "q": "Bakım türündeki sözleşmelerin toplam yıllık bedeli ne kadar?",
        "sql": "SELECT SUM(annual_value_try) FROM contracts_meta WHERE contract_type = 'bakim'",
        "tags": [],
        "compute": lambda rows: [
            [sum(_dec(r[7]) for r in rows["contracts_meta"] if r[4] == "bakim")]
        ],
    },
    {
        "q": "2025 yılında cihaz arızaları nedeniyle en uzun kesinti yaşayan bölüm hangisi?",
        "sql": "SELECT d.name_tr, SUM(f.downtime_hours) AS kesinti FROM device_faults f JOIN "
        "devices v ON v.id = f.device_id JOIN departments d ON d.id = v.department_id WHERE "
        "f.reported_on BETWEEN '2025-01-01' AND '2025-12-31' GROUP BY d.name_tr "
        "ORDER BY kesinti DESC LIMIT 1",
        "tags": ["join", "group", "date"],
        "compute": _top_downtime_department,
    },
    {
        "q": "Pediatri bölümünde 2025'te bir günde en fazla kaç yatak dolu oldu?",
        "sql": "SELECT MAX(a.occupied_beds) FROM admissions a JOIN departments d ON d.id = "
        "a.department_id WHERE d.code = 'PEDI'",
        "tags": ["join"],
        "compute": lambda rows: [
            [max(a[5] for a in rows["admissions"] if a[1] == _dep(rows, PEDI)[0])]
        ],
    },
    {
        "q": "3. kattaki bölümlerin toplam yatak kapasitesi kaçtır?",
        "sql": "SELECT SUM(bed_capacity) FROM departments WHERE floor = 3",
        "tags": [],
        "compute": lambda rows: [[sum(r[4] for r in rows["departments"] if r[3] == 3)]],
    },
]

# Statements mcp-sql must refuse; `expected_code` is the merged 05a validator's SqlRejected code
# (checked by backend/tests/unit/test_18td_sql_write_attempts.py, K-SEN-0002; a closed-list
# function is sql_function_not_allowed since 05a review r1).
# `class`: write = a plain write statement;
# hidden_write = a statement that would write, disguised (`patterns`: union, cte, comment,
# function, second_statement, select_into; review r1 MAJOR-1: every one of them really tries to
# write); catalog = reads the system catalog or calls a system function, no write.
# The demo schema has no sequence (integer keys), so the function case writes a large object
# (lo_create); test_18_f3_7 checks that sequences and large objects are unchanged.
WRITE_ATTEMPTS = [
    ("DELETE FROM device_faults", "write", "sql_not_select", []),
    ("UPDATE devices SET status = 'hurda'", "write", "sql_not_select", []),
    (
        "INSERT INTO departments (id, code, name_tr, floor, bed_capacity) "
        "VALUES (99, 'TEST', 'Deneme', 9, 1)",
        "write",
        "sql_not_select",
        [],
    ),
    ("DROP TABLE beds", "write", "sql_not_select", []),
    ("TRUNCATE admissions", "write", "sql_not_select", []),
    ("ALTER TABLE devices ADD COLUMN note text", "write", "sql_not_select", []),
    (
        "WITH d AS (DELETE FROM device_faults RETURNING id) SELECT COUNT(*) FROM d",
        "hidden_write",
        "sql_not_select",
        ["cte"],
    ),
    ("SELECT 1; DELETE FROM beds", "hidden_write", "sql_multiple_statements", ["second_statement"]),
    (
        "SELECT 1 /* rapor */; DROP TABLE devices",
        "hidden_write",
        "sql_multiple_statements",
        ["comment", "second_statement"],
    ),
    ("SELECT * INTO beds_copy FROM beds", "hidden_write", "sql_not_select", ["select_into"]),
    (
        "WITH d AS (UPDATE devices SET status = 'hurda' RETURNING id) "
        "SELECT id FROM d UNION SELECT id FROM beds",
        "hidden_write",
        "sql_not_select",
        ["union", "cte"],
    ),
    (
        "SELECT id FROM departments UNION ALL SELECT lo_create(0)::int",
        "hidden_write",
        "sql_function_not_allowed",
        ["union", "function"],
    ),
    (
        "SELECT code FROM departments -- rapor\n; INSERT INTO beds "
        "(id, department_id, bed_code, bed_type, is_active) "
        "VALUES (9999, 1, 'X-1', 'standart', TRUE)",
        "hidden_write",
        "sql_multiple_statements",
        ["comment", "second_statement"],
    ),
    (
        "SELECT code FROM departments UNION SELECT usename FROM pg_user",
        "catalog",
        "sql_system_catalog",
        ["union"],
    ),
    ("SELECT pg_sleep(30)", "catalog", "sql_function_not_allowed", []),
]

SUITE = {
    "key": "sql-20",
    "name": "Salt okunur veri sorgusu sınavı (20 soru, F3)",
    "langfuse_dataset_name": "sql-20",
    "scorers": ["sql_result", "contains"],
    "pass_threshold": 0.8,
    "repeat": 1,
}


def questions() -> list[dict]:
    out = []
    for q in eval_set.SQL_QUESTIONS:
        out.append(
            {
                "q": q["q"],
                "sql": q["sql"],
                "tags": ORIGIN_TAGS[q["id"]],
                "origin": f"sozlesme-33/{q['id']}",
                "compute": lambda rows, q=q: [[q["compute"](rows)]],
            }
        )
    out.extend(NEW_QUESTIONS)
    return [{"id": f"sql-{n:02d}", **q} for n, q in enumerate(out, start=1)]


def result_rows(q: dict, rows: dict) -> list[list]:
    """The expected result as JSON values. An empty result, a NULL cell or a lone 0 is an
    error: a model that finds nothing would pass such a question by chance."""
    result = q["compute"](rows)
    if not result or any(cell is None for row in result for cell in row):
        raise ValueError(f"{q['id']}: empty or NULL expected result")
    if result == [[0]]:
        raise ValueError(f"{q['id']}: expected result 0 cannot tell a right answer from none")
    return [[str(c) if isinstance(c, Decimal) else c for c in row] for row in result]


def item(q: dict, rows: dict) -> dict:
    result = result_rows(q, rows)
    if len(result) == 1:
        must = [str(c) for c in result[0]]
        answer = " - ".join(must)
    else:
        must = [str(row[0]) for row in result]
        answer = "; ".join(" - ".join(str(c) for c in row) for row in result)
    tags = ["sql", *q["tags"]]
    if len(result) > 1 and "multi_row" not in tags:
        raise ValueError(f"{q['id']}: multi-row result without the multi_row tag")
    metadata = {
        "tags": tags,
        "answerable": True,
        "style": "dogrudan",
        "expected_docs": [],
        "reference_sql": q["sql"],
    }
    if "origin" in q:
        metadata["origin"] = q["origin"]
    return {
        "id": q["id"],
        "input": {"message": q["q"], "variables": {}},
        "expected_output": {"answer": answer, "must_contain": must, "sql_result": result},
        "metadata": metadata,
    }


def _json(data) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def generate(rng: random.Random, out: Path, seed: int) -> None:
    # rng is unused: the data is computed from the schema module's own stream, so it equals
    # what seed.sql holds.
    rows = schema.build(random.Random(f"{seed}:schema"))
    base = out / "eval"
    write_text(base / "sql-20.json", _json([item(q, rows) for q in questions()]))
    write_text(base / "suite-sql-20.json", _json(SUITE))
    attempts = [
        {"id": f"w{n:02d}", "sql": sql, "class": cls, "expected_code": code, "patterns": pats}
        for n, (sql, cls, code, pats) in enumerate(WRITE_ATTEMPTS, start=1)
    ]
    write_text(base / "sql-write-attempts.json", _json(attempts))
