"""F13 data (plan/18): dated second versions of two 13a contracts.

v1 is 13a's own file under contracts/ (not copied). v2 is built from the very same blocks:
contracts.render_all() is replayed on 13a's random stream ("<seed>:contracts"), so the only
differences are one changed clause and a version note at the top. The changed clauses are not
asked by the F1 exam (sozlesme-33), so indexing v2 in its own knowledge base for F13 leaves F1
untouched; test_18_f13_3 checks that.
"""

import json
import random
from pathlib import Path

from . import contracts, docx, write_text

EFFECTIVE = "2025-09-01"

CHANGES = [
    {
        "code": "SZL-2025-003",
        "clause": "5.2",
        "old": "Her vardiyada en az 48 temizlik görevlisi çalıştırılır.",
        "new": "Her vardiyada en az 56 temizlik görevlisi çalıştırılır.",
        "v1_value": "48",
        "v2_value": "56",
        "question": "Temizlik hizmet sözleşmesine göre her vardiyada en az kaç temizlik "
        "görevlisi çalıştırılır?",
    },
    {
        "code": "SZL-2025-007",
        "clause": "7.1",
        "old": "gecikilen sipariş tutarının %0,3'ü oranında",
        "new": "gecikilen sipariş tutarının %0,5'i oranında",
        "v1_value": "%0,3",
        "v2_value": "%0,5",
        "question": "Laboratuvar kiti tedarik sözleşmesinde teslimatta gecikilen her gün için "
        "uygulanan cezai şart oranı nedir?",
    },
]


def _date(iso: str) -> str:
    y, m, d = iso.split("-")
    return f"{d}.{m}.{y}"


def v2_blocks(content: list[tuple], change: dict) -> list[tuple]:
    """content with exactly one paragraph changed and the version note after the header."""
    out, hits = [], 0
    for kind, value in content:
        if kind == "p" and change["old"] in value:
            value = value.replace(change["old"], change["new"])
            hits += 1
        out.append((kind, value))
    if hits != 1:
        raise ValueError(f"{change['code']}: clause text found {hits} times, expected 1")
    note = (
        "p",
        f"Sürüm 2. Yürürlük tarihi: {_date(EFFECTIVE)}. Bu sürüm önceki sürümün yerine geçer; "
        f"değişen madde: {change['clause']}.",
    )
    return out[:2] + [note] + out[2:]


def v2_name(file_name: str) -> str:
    stem, ext = file_name.rsplit(".", 1)
    return f"{stem}_v2.{ext}"


def build(seed: int) -> list[dict]:
    rendered = {
        c["code"]: (c, content, data)
        for c, content, data in contracts.render_all(random.Random(f"{seed}:contracts"))
    }
    out = []
    for change in CHANGES:
        c, content, v1_bytes = rendered[change["code"]]
        if c["format"] != "docx":
            raise ValueError(f"{c['code']}: only DOCX contracts are versioned here")
        blocks = v2_blocks(content, change)
        out.append(
            {
                "contract": c,
                "change": change,
                "v1_bytes": v1_bytes,
                "v1_blocks": content,
                "v2_blocks": blocks,
                "v2_bytes": docx.render(blocks, f"{c['title']} - Sürüm 2"),
            }
        )
    return out


def generate(rng: random.Random, out: Path, seed: int) -> None:
    # rng is unused: v2 must replay 13a's own contracts stream (see module docstring).
    base = out / "versions"
    base.mkdir(parents=True, exist_ok=True)
    expected = []
    for v in build(seed):
        c, change = v["contract"], v["change"]
        (base / v2_name(c["file_name"])).write_bytes(v["v2_bytes"])
        expected.append(
            {
                "code": c["code"],
                "v1_file": f"contracts/{c['file_name']}",
                "v2_file": f"versions/{v2_name(c['file_name'])}",
                "v2_effective_date": EFFECTIVE,
                "changed_clause": change["clause"],
                "v1_value": change["v1_value"],
                "v2_value": change["v2_value"],
                "question": change["question"],
                # the answer is built from v2 and names its date; v1's value may appear only
                # as the previous value (06a prompt rule, PayCore D5)
                "must_contain": [change["v2_value"], _date(EFFECTIVE)],
                "v1_value_only_as_previous": True,
            }
        )
    write_text(base / "expected.json", json.dumps(expected, ensure_ascii=False, indent=2) + "\n")
