"""Demo "agent presentation DB" (plan/13 item 2): schema, 10,000 seed rows,
schema_descriptions (plan/05 B) and 20 few-shot question/SQL pairs.

Only aggregates and codes; no person-level row or column (data boundary, CONTRACTS).
"""

import datetime as dt
import json
import random
from pathlib import Path

from . import write_text
from .words import (
    BED_TYPES,
    CONTRACTS,
    DEPARTMENTS,
    DEVICE_STATUSES,
    DEVICE_TYPES,
    FAULT_TYPES,
    SEVERITIES,
)

N_BEDS = 400
N_DEVICES = 600
N_FAULTS = 1675
YEAR = 2025  # admissions: one row per department per day of YEAR (20 x 365 = 7,300)
TOTAL_ROWS = 10_000
DEVICE_VENDORS = [
    "Tavlan Medikal Teknik A.Ş.",
    "Arkada Tıp Cihazları A.Ş.",
    "Selvi Elektromedikal Ltd. Şti.",
]

# (table, [(column, sql type)]) in creation order
TABLES = [
    (
        "departments",
        [
            ("id", "integer PRIMARY KEY"),
            ("code", "varchar(8) NOT NULL UNIQUE"),
            ("name_tr", "varchar(64) NOT NULL"),
            ("floor", "smallint NOT NULL"),
            ("bed_capacity", "integer NOT NULL"),
        ],
    ),
    (
        "beds",
        [
            ("id", "integer PRIMARY KEY"),
            ("department_id", "integer NOT NULL REFERENCES departments(id)"),
            ("bed_code", "varchar(16) NOT NULL UNIQUE"),
            ("bed_type", "varchar(16) NOT NULL"),
            ("is_active", "boolean NOT NULL"),
        ],
    ),
    (
        "admissions",
        [
            ("id", "integer PRIMARY KEY"),
            ("department_id", "integer NOT NULL REFERENCES departments(id)"),
            ("day", "date NOT NULL"),
            ("admitted_count", "integer NOT NULL"),
            ("discharged_count", "integer NOT NULL"),
            ("occupied_beds", "integer NOT NULL"),
        ],
    ),
    (
        "devices",
        [
            ("id", "integer PRIMARY KEY"),
            ("department_id", "integer NOT NULL REFERENCES departments(id)"),
            ("device_code", "varchar(16) NOT NULL UNIQUE"),
            ("device_type", "varchar(32) NOT NULL"),
            ("vendor", "varchar(128) NOT NULL"),
            ("installed_on", "date NOT NULL"),
            ("status", "varchar(16) NOT NULL"),
        ],
    ),
    (
        "device_faults",
        [
            ("id", "integer PRIMARY KEY"),
            ("device_id", "integer NOT NULL REFERENCES devices(id)"),
            ("reported_on", "date NOT NULL"),
            ("fault_type", "varchar(32) NOT NULL"),
            ("severity", "varchar(16) NOT NULL"),
            ("resolved_on", "date"),
            ("downtime_hours", "numeric(6,1) NOT NULL"),
        ],
    ),
    (
        "contracts_meta",
        [
            ("id", "integer PRIMARY KEY"),
            ("contract_code", "varchar(16) NOT NULL UNIQUE"),
            ("title", "varchar(160) NOT NULL"),
            ("vendor", "varchar(128) NOT NULL"),
            ("contract_type", "varchar(32) NOT NULL"),
            ("start_date", "date NOT NULL"),
            ("end_date", "date NOT NULL"),
            ("annual_value_try", "numeric(14,2) NOT NULL"),
            ("notice_days", "integer NOT NULL"),
            ("file_name", "varchar(128) NOT NULL"),
        ],
    ),
]
COLUMNS = {t: [c for c, _ in cols] for t, cols in TABLES}


def _split(total: int, parts: int, rng: random.Random, low: int) -> list[int]:
    """Split total into parts integers >= low, deterministic for rng."""
    sizes = [low] * parts
    for _ in range(total - low * parts):
        sizes[rng.randrange(parts)] += 1
    return sizes


def _day(offset: int) -> str:
    return (dt.date(YEAR, 1, 1) + dt.timedelta(days=offset)).isoformat()


def build(rng: random.Random) -> dict[str, list[tuple]]:
    """All seed rows, keyed by table. Eval expectations are computed from this too."""
    rows: dict[str, list[tuple]] = {}

    capacities = _split(N_BEDS, len(DEPARTMENTS), rng, low=8)
    rows["departments"] = [
        (i + 1, code, name, 1 + i // 3, capacities[i]) for i, (code, name) in enumerate(DEPARTMENTS)
    ]

    beds = []
    for dep_id, code, _, _, cap in rows["departments"]:
        for n in range(cap):
            bed_type = (
                "yogun_bakim" if code == "YBAK" else rng.choices(BED_TYPES, weights=[85, 5, 10])[0]
            )
            beds.append(
                (len(beds) + 1, dep_id, f"{code}-{n + 1:03d}", bed_type, rng.random() > 0.04)
            )
    rows["beds"] = beds

    admissions = []
    days = (dt.date(YEAR, 12, 31) - dt.date(YEAR, 1, 1)).days + 1
    for dep_id, _, _, _, cap in rows["departments"]:
        occupied = cap // 2
        for d in range(days):
            weekend = (dt.date(YEAR, 1, 1) + dt.timedelta(days=d)).weekday() >= 5
            admitted = rng.randint(0, max(1, cap // (6 if weekend else 3)))
            discharged = rng.randint(0, max(1, cap // (5 if weekend else 3)))
            occupied = max(0, min(cap, occupied + admitted - discharged))
            admissions.append(
                (len(admissions) + 1, dep_id, _day(d), admitted, discharged, occupied)
            )
    rows["admissions"] = admissions

    devices = []
    for n in range(N_DEVICES):
        dep_id = rng.randint(1, len(DEPARTMENTS))
        dtype = rng.choice(DEVICE_TYPES)
        installed = dt.date(2016, 1, 1) + dt.timedelta(days=rng.randrange(9 * 365))
        status = rng.choices(DEVICE_STATUSES, weights=[88, 8, 4])[0]
        devices.append(
            (
                n + 1,
                dep_id,
                f"CHZ-{n + 1:05d}",
                dtype,
                rng.choice(DEVICE_VENDORS),
                installed.isoformat(),
                status,
            )
        )
    rows["devices"] = devices

    faults = []
    for n in range(N_FAULTS):
        device_id = rng.randint(1, N_DEVICES)
        reported = rng.randrange(days)
        severity = rng.choices(SEVERITIES, weights=[40, 35, 18, 7])[0]
        resolved = reported + rng.randint(0, 20)
        resolved_on = _day(resolved) if resolved < days and rng.random() > 0.06 else None
        downtime = round(rng.uniform(0.5, 6.0) * (1 + SEVERITIES.index(severity)), 1)
        faults.append(
            (
                n + 1,
                device_id,
                _day(reported),
                rng.choice(FAULT_TYPES),
                severity,
                resolved_on,
                downtime,
            )
        )
    rows["device_faults"] = faults

    rows["contracts_meta"] = [
        (
            i + 1,
            c["code"],
            c["title"],
            c["vendor"],
            c["contract_type"],
            c["start_date"],
            c["end_date"],
            c["annual_value_try"],
            c["notice_days"],
            c["file_name"],
        )
        for i, c in enumerate(CONTRACTS)
    ]

    total = sum(len(r) for r in rows.values())
    if total != TOTAL_ROWS:
        raise ValueError(f"seed row count {total} != {TOTAL_ROWS}")
    return rows


def _sql_value(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


def schema_sql() -> str:
    parts = [
        "-- FFCore demo agent presentation DB (synthetic, package 13a).",
        "-- Aggregates and codes only; no person-level data.",
        "",
    ]
    for table, cols in TABLES:
        body = ",\n".join(f"  {c} {t}" for c, t in cols)
        parts.append(f"CREATE TABLE {table} (\n{body}\n);\n")
    return "\n".join(parts)


def seed_sql(rows: dict[str, list[tuple]], batch: int = 500) -> str:
    out = ["-- Generated by data/samples/scripts/generate.py; do not edit.", "BEGIN;", ""]
    for table, _ in TABLES:
        data = rows[table]
        for start in range(0, len(data), batch):
            chunk = data[start : start + batch]
            out.append(f"INSERT INTO {table} ({', '.join(COLUMNS[table])}) VALUES")
            lines = ["(" + ", ".join(_sql_value(v) for v in r) + ")" for r in chunk]
            out.append(",\n".join(lines) + ";")
            out.append("")
    out.append("COMMIT;")
    return "\n".join(out) + "\n"


READONLY_ROLE_SQL = """\
-- Read-only role template for mcp-sql (plan/05 B). No password here: the login
-- user and its secret are created by the installer from .env, then granted this role.
CREATE ROLE agent_readonly NOLOGIN;
GRANT USAGE ON SCHEMA public TO agent_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO agent_readonly;
ALTER ROLE agent_readonly SET statement_timeout = '20s';
ALTER ROLE agent_readonly SET default_transaction_read_only = on;
"""

TABLE_DESCRIPTIONS = {
    "departments": "Hastane bölümleri (klinik birimler) ve yatak kapasiteleri.",
    "beds": "Bölümlere ait yataklar; tür ve kullanımda olup olmadığı.",
    "admissions": "Bölüm başına günlük yatış özeti: yatış, taburcu ve dolu yatak sayıları (kişi "
    "düzeyi değil).",
    "devices": "Tıbbi cihaz envanteri; bölüm, tür, üretici ve durum.",
    "device_faults": "Cihaz arıza kayıtları; arıza türü, önem, çözüm tarihi ve kesinti süresi.",
    "contracts_meta": "Tedarikçi sözleşmelerinin özet bilgileri; belge dosyası bilgi tabanındadır.",
}

# (table, column) -> (description_tr, formula or None)
COLUMN_DESCRIPTIONS = {
    ("departments", "id"): ("Bölüm kimliği.", None),
    ("departments", "code"): ("Bölümün kısa kodu (ör. KARD).", None),
    ("departments", "name_tr"): ("Bölümün Türkçe adı.", None),
    ("departments", "floor"): ("Bölümün bulunduğu kat.", None),
    ("departments", "bed_capacity"): ("Bölümün toplam yatak kapasitesi.", "SUM(bed_capacity)"),
    ("beds", "id"): ("Yatak kimliği.", None),
    ("beds", "department_id"): ("Yatağın bağlı olduğu bölüm (departments.id).", None),
    ("beds", "bed_code"): ("Yatak kodu: bölüm kodu ve sıra numarası.", None),
    ("beds", "bed_type"): ("Yatak türü: standart, yogun_bakim, izolasyon.", None),
    ("beds", "is_active"): ("Yatak kullanımda mı (FALSE = hizmet dışı).", None),
    ("admissions", "id"): ("Kayıt kimliği.", None),
    ("admissions", "department_id"): ("Bölüm (departments.id).", None),
    ("admissions", "day"): ("Özetin ait olduğu gün.", None),
    ("admissions", "admitted_count"): (
        "O gün bölüme yatırılan hasta sayısı.",
        "SUM(admitted_count)",
    ),
    ("admissions", "discharged_count"): (
        "O gün bölümden taburcu edilen hasta sayısı.",
        "SUM(discharged_count)",
    ),
    ("admissions", "occupied_beds"): (
        "Gün sonunda dolu yatak sayısı. Doluluk oranı = occupied_beds / departments.bed_capacity.",
        "AVG(occupied_beds::numeric / departments.bed_capacity)",
    ),
    ("devices", "id"): ("Cihaz kimliği.", None),
    ("devices", "department_id"): ("Cihazın bulunduğu bölüm (departments.id).", None),
    ("devices", "device_code"): ("Cihaz envanter kodu (CHZ-xxxxx).", None),
    ("devices", "device_type"): ("Cihaz türü (ör. ventilator, infuzyon_pompasi).", None),
    ("devices", "vendor"): ("Cihazın üreticisi ya da tedarikçisi.", None),
    ("devices", "installed_on"): ("Kurulum tarihi.", None),
    ("devices", "status"): ("Cihaz durumu: aktif, bakimda, hurda.", None),
    ("device_faults", "id"): ("Arıza kaydı kimliği.", None),
    ("device_faults", "device_id"): ("Arızalanan cihaz (devices.id).", None),
    ("device_faults", "reported_on"): ("Arızanın bildirildiği gün.", None),
    ("device_faults", "fault_type"): ("Arıza türü (elektriksel, mekanik, yazilim...).", None),
    ("device_faults", "severity"): ("Önem: dusuk, orta, yuksek, kritik.", None),
    ("device_faults", "resolved_on"): ("Çözüldüğü gün; NULL ise açık arıza.", None),
    ("device_faults", "downtime_hours"): (
        "Arıza nedeniyle cihazın hizmet dışı kaldığı saat.",
        "SUM(downtime_hours)",
    ),
    ("contracts_meta", "id"): ("Sözleşme kimliği.", None),
    ("contracts_meta", "contract_code"): ("Sözleşme numarası (SZL-yyyy-nnn).", None),
    ("contracts_meta", "title"): ("Sözleşme başlığı.", None),
    ("contracts_meta", "vendor"): ("Karşı taraf firma.", None),
    ("contracts_meta", "contract_type"): (
        "Tür: bakim, hizmet, tedarik, lisans, danismanlik.",
        None,
    ),
    ("contracts_meta", "start_date"): ("Başlangıç tarihi.", None),
    ("contracts_meta", "end_date"): ("Bitiş tarihi.", None),
    ("contracts_meta", "annual_value_try"): (
        "Yıllık sözleşme bedeli (TL, KDV hariç).",
        "SUM(annual_value_try)",
    ),
    ("contracts_meta", "notice_days"): ("Fesih bildirim süresi (gün).", None),
    ("contracts_meta", "file_name"): ("Bilgi tabanındaki belge dosyasının adı.", None),
}

FEW_SHOTS = [
    (
        "Kardiyoloji bölümünün yatak kapasitesi nedir?",
        "SELECT bed_capacity FROM departments WHERE code = 'KARD'",
    ),
    (
        "Hangi bölümün yatak kapasitesi en yüksek?",
        "SELECT name_tr, bed_capacity FROM departments ORDER BY bed_capacity DESC LIMIT 1",
    ),
    (
        "Hizmet dışı kaç yatak var?",
        "SELECT COUNT(*) AS hizmet_disi FROM beds WHERE is_active = FALSE",
    ),
    (
        "Yatak türlerine göre yatak sayıları nedir?",
        "SELECT bed_type, COUNT(*) AS adet FROM beds GROUP BY bed_type ORDER BY adet DESC",
    ),
    (
        "2025 yılında toplam kaç yatış yapıldı?",
        "SELECT SUM(admitted_count) AS toplam_yatis FROM admissions WHERE day BETWEEN "
        "'2025-01-01' AND '2025-12-31'",
    ),
    (
        "Mart 2025'te en çok yatış alan üç bölüm hangileri?",
        "SELECT d.name_tr, SUM(a.admitted_count) AS yatis FROM admissions a JOIN departments d ON "
        "d.id = a.department_id WHERE a.day BETWEEN '2025-03-01' AND '2025-03-31' GROUP BY "
        "d.name_tr ORDER BY yatis DESC LIMIT 3",
    ),
    (
        "Nöroloji bölümünün 2025 ortalama doluluk oranı nedir?",
        "SELECT ROUND(AVG(a.occupied_beds::numeric / d.bed_capacity), 3) AS doluluk FROM "
        "admissions a JOIN departments d ON d.id = a.department_id WHERE d.code = 'NORO'",
    ),
    (
        "Aylık toplam taburcu sayıları nedir?",
        "SELECT date_trunc('month', day)::date AS ay, SUM(discharged_count) AS taburcu FROM "
        "admissions GROUP BY ay ORDER BY ay",
    ),
    (
        "Hafta sonları ortalama günlük yatış kaçtır?",
        "SELECT ROUND(AVG(gunluk), 1) AS ortalama FROM (SELECT day, SUM(admitted_count) AS gunluk "
        "FROM admissions WHERE EXTRACT(ISODOW FROM day) IN (6, 7) GROUP BY day) t",
    ),
    (
        "Kaç ventilatör aktif durumda?",
        "SELECT COUNT(*) AS adet FROM devices "
        "WHERE device_type = 'ventilator' AND status = 'aktif'",
    ),
    (
        "Cihaz türlerine göre envanter dağılımı nedir?",
        "SELECT device_type, COUNT(*) AS adet FROM devices GROUP BY device_type ORDER BY adet DESC",
    ),
    (
        "Hangi üreticinin cihazı en çok arıza verdi?",
        "SELECT v.vendor, COUNT(*) AS ariza FROM device_faults f JOIN devices v ON v.id = "
        "f.device_id GROUP BY v.vendor ORDER BY ariza DESC LIMIT 1",
    ),
    (
        "Şu an çözülmemiş kaç arıza var?",
        "SELECT COUNT(*) AS acik_ariza FROM device_faults WHERE resolved_on IS NULL",
    ),
    (
        "Kritik önemdeki arızaların toplam kesinti süresi kaç saat?",
        "SELECT SUM(downtime_hours) AS kesinti_saat FROM device_faults WHERE severity = 'kritik'",
    ),
    (
        "Yoğun bakımdaki cihazların arıza sayısı nedir?",
        "SELECT COUNT(*) AS ariza FROM device_faults f JOIN devices v ON v.id = f.device_id JOIN "
        "departments d ON d.id = v.department_id WHERE d.code = 'YBAK'",
    ),
    (
        "Arızaların ortalama çözüm süresi kaç gün?",
        "SELECT ROUND(AVG(resolved_on - reported_on), 1) AS ortalama_gun FROM device_faults WHERE "
        "resolved_on IS NOT NULL",
    ),
    (
        "Arıza türlerine göre ortalama kesinti süresi nedir?",
        "SELECT fault_type, ROUND(AVG(downtime_hours), 1) AS ortalama_saat FROM device_faults "
        "GROUP BY fault_type ORDER BY ortalama_saat DESC",
    ),
    (
        "Yıllık bedeli en yüksek sözleşme hangisi?",
        "SELECT contract_code, title, annual_value_try FROM contracts_meta ORDER BY "
        "annual_value_try DESC LIMIT 1",
    ),
    (
        "2026 yılında sona erecek sözleşmeler hangileri?",
        "SELECT contract_code, title, end_date FROM contracts_meta WHERE end_date BETWEEN "
        "'2026-01-01' AND '2026-12-31' ORDER BY end_date",
    ),
    (
        "Sözleşmelerin toplam yıllık bedeli ne kadar?",
        "SELECT SUM(annual_value_try) AS toplam_bedel FROM contracts_meta",
    ),
]


def descriptions(rows: dict[str, list[tuple]]) -> list[dict]:
    out = []
    for table, cols in TABLES:
        out.append(
            {
                "table_name": table,
                "column_name": None,
                "description_tr": TABLE_DESCRIPTIONS[table],
                "sample_values": [],
                "is_metric": False,
                "formula": None,
            }
        )
        for idx, (col, _) in enumerate(cols):
            desc, formula = COLUMN_DESCRIPTIONS[(table, col)]
            samples = []
            for r in rows[table]:
                v = r[idx]
                if v is not None and str(v) not in samples:
                    samples.append(str(v))
                if len(samples) == 3:
                    break
            out.append(
                {
                    "table_name": table,
                    "column_name": col,
                    "description_tr": desc,
                    "sample_values": samples,
                    "is_metric": formula is not None,
                    "formula": formula,
                }
            )
    return out


def _json(data) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def generate(rng: random.Random, out: Path, seed: int) -> None:
    rows = build(rng)
    base = out / "schema"
    write_text(base / "schema.sql", schema_sql())
    write_text(base / "seed.sql", seed_sql(rows))
    write_text(base / "readonly_role.sql", READONLY_ROLE_SQL)
    write_text(base / "schema_descriptions.json", _json(descriptions(rows)))
    write_text(base / "few_shots.json", _json([{"question": q, "sql": s} for q, s in FEW_SHOTS]))
