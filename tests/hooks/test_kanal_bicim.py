"""KANAL-BICIM rule (fix/ajan-hooklari-2 D1, FOLLOWUP-189 a, K-HOOK2-0001/0002).

New `### ` headers added to `state/kanal/<rol>.md` must follow
handbook/MULTI_AGENT_PROTOCOL.md "Mesaj biçimi"; old content is never judged.
The guard's closed lists are pinned to the protocol by a drift test.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from conftest import REPO_ROOT, SESSION_ID, base_env, run_hook

PROTOCOL = REPO_ROOT / "handbook" / "MULTI_AGENT_PROTOCOL.md"
SHA = "7a1195afc17648062a0a6afdae45d2aa54d88bd9"
PREAMBLE = "# Kanal: isci-b\n\n- Durum: ACTIVE\n\n## Mesajlar\n"
OK_MSG = (
    "### B-HOOK2-0009 · 2026-11-16 22:40 · → koordinator · ACK\n"
    "Paket: fix/ajan-hooklari-2 · Cevap: K-HOOK2-0001\n"
    "gövde\n"
)


def kanal(main_root: Path, rol: str = "isci-b", text: str = PREAMBLE) -> Path:
    path = main_root / "state" / "kanal" / f"{rol}.md"
    path.write_text(text, encoding="utf-8")
    return path


def write(path: Path, content: str) -> dict:
    return {
        "session_id": SESSION_ID,
        "tool_name": "Write",
        "tool_input": {"file_path": str(path), "content": content},
    }


def edit(path: Path, old: str, new: str, replace_all: bool = False) -> dict:
    inp = {"file_path": str(path), "old_string": old, "new_string": new}
    if replace_all:
        inp["replace_all"] = True
    return {"session_id": SESSION_ID, "tool_name": "Edit", "tool_input": inp}


def multiedit(path: Path, edits: list[tuple[str, str]]) -> dict:
    return {
        "session_id": SESSION_ID,
        "tool_name": "MultiEdit",
        "tool_input": {
            "file_path": str(path),
            "edits": [{"old_string": o, "new_string": n} for o, n in edits],
        },
    }


def violations(guard, payload, main_root, rol="isci-b"):
    return [
        v for v in guard.decide(payload, base_env(main_root, FFCORE_ROL=rol))
        if v.rule == "KANAL-BICIM"
    ]


def appended(guard, main_root, msg: str, rol: str = "isci-b"):
    path = kanal(main_root, rol)
    return violations(guard, edit(path, "## Mesajlar\n", "## Mesajlar\n\n" + msg), main_root, rol)


def msg(header: str, second: str) -> str:
    return f"{header}\n{second}\ngövde\n"


H = "### B-HOOK2-0009 · 2026-11-16 22:40 · → koordinator · "
P = "Paket: fix/ajan-hooklari-2 · Cevap: K-HOOK2-0001"


# --- valid ------------------------------------------------------------------


def test_valid_ack_edit_allowed(guard, main_root):
    assert appended(guard, main_root, OK_MSG) == []


def test_valid_write_allowed(guard, main_root):
    path = kanal(main_root)
    assert violations(guard, write(path, PREAMBLE + "\n" + OK_MSG), main_root) == []


@pytest.mark.parametrize(
    ("tur", "second"),
    [
        ("PR-HAZIR", f"{P} · SHA: {SHA}"),
        ("REVIEW-SONUC", f"{P} · SHA: {SHA} · Sonuc: ONAY · Bulgu: B0 M0 m3 N5"),
        ("DURUM", f"{P} · Durum: PLANNED"),
        ("DURUM", f"{P} · Durum: DUYURU"),
        ("YIGIN-AC", f"{P} · Yigin: ffb10c1"),
        ("ACK", "Paket: - · Cevap: -"),
        ("CEVAP", "Paket: 09 · Cevap: K-09-0001, K-09-0002"),
        ("DURUM", f"{P} · Durum: VERIFIED · Not: ek alan serbest"),
    ],
)
def test_valid_typed_fields_allowed(guard, main_root, tur, second):
    assert appended(guard, main_root, msg(H + tur, second)) == []


def test_kullanici_allowed_in_coordinator_channel(guard, main_root):
    m = msg("### K-GEN-0099 · 2026-11-16 22:40 · → kullanici · DURUM", "Paket: - · Cevap: - · Durum: DUYURU")
    assert appended(guard, main_root, m, rol="koordinator") == []


# --- invalid header ---------------------------------------------------------


@pytest.mark.parametrize(
    ("header", "field"),
    [
        (H + "YIGIN-AÇ", "tür"),
        (H + "DURUM (ölçüm)", "tür"),
        ("### B-HOOK2-0009 · 2026-11-16 22:40 · → koordinatör · ACK", "alıcı"),
        ("### B-HOOK2-0009 · 2026-11-16 22:40 · → isci-b (09) · ACK", "alıcı"),
        ("### B-0009 · 2026-11-16 22:40 · → koordinator · ACK", "ID"),
        ("### B-HOOK2-0009 · 2026-11-16 · → koordinator · ACK", "tarih"),
        ("### B-HOOK2-0009 · 16.11.2026 22:40 · → koordinator · ACK", "tarih"),
        ("### B-HOOK2-0009 — 2026-11-16 22:40 — koordinator — ACK", "başlık"),
    ],
)
def test_invalid_header_blocked(guard, main_root, header, field):
    found = appended(guard, main_root, msg(header, P))
    assert len(found) == 1, found
    assert field in found[0].message, found[0].message


def test_kullanici_blocked_in_worker_channel(guard, main_root):
    found = appended(guard, main_root, msg("### B-HOOK2-0009 · 2026-11-16 22:40 · → kullanici · ACK", P))
    assert found and "kullanici" in found[0].message


# --- invalid second line ----------------------------------------------------


@pytest.mark.parametrize(
    ("tur", "second", "field"),
    [
        ("ACK", "gövde hemen başlıyor", "Paket"),
        ("ACK", "Paket: fix/x", "Cevap"),
        ("ACK", "Paket: fix/x · Cevap: foo", "Cevap"),
        ("PR-HAZIR", P, "SHA"),
        ("PR-HAZIR", f"{P} · SHA: 7a1195a", "SHA"),
        ("REVIEW-ISTEK", f"{P} · SHA: {SHA[:-1]}X", "SHA"),
        ("REVIEW-SONUC", f"{P} · SHA: {SHA} · Bulgu: B0 M0 m0 N0", "Sonuc"),
        ("REVIEW-SONUC", f"{P} · SHA: {SHA} · Sonuc: OK · Bulgu: B0 M0 m0 N0", "Sonuc"),
        ("REVIEW-SONUC", f"{P} · SHA: {SHA} · Sonuc: ONAY · Bulgu: 0 bulgu", "Bulgu"),
        ("DURUM", P, "Durum"),
        ("DURUM", f"{P} · Durum: WARN-GUNU", "Durum"),
        ("YIGIN-KAPA", P, "Yigin"),
        ("ONAY-TEYIT", P, "SHA"),
    ],
)
def test_invalid_second_line_blocked(guard, main_root, tur, second, field):
    found = appended(guard, main_root, msg(H + tur, second))
    assert len(found) == 1, found
    assert field in found[0].message, found[0].message


def test_header_as_last_line_blocked(guard, main_root):
    path = kanal(main_root)
    found = violations(guard, write(path, PREAMBLE + "\n" + H + "ACK"), main_root)
    assert found and "Paket" in found[0].message


# --- only additions are judged ------------------------------------------------


OLD_BAD = "### B-09-0001 · 2026-11-04 10:00 · → koordinatör · YIGIN-AÇ (eski)\nserbest\n"


def test_old_malformed_header_untouched_allowed(guard, main_root):
    path = kanal(main_root, text=PREAMBLE + OLD_BAD)
    assert violations(guard, edit(path, "serbest\n", "serbest\n\n" + OK_MSG), main_root) == []


def test_write_keeping_old_malformed_allowed(guard, main_root):
    path = kanal(main_root, text=PREAMBLE + OLD_BAD)
    assert violations(guard, write(path, PREAMBLE + OLD_BAD + "\n" + OK_MSG), main_root) == []


def test_lease_line_edit_allowed(guard, main_root):
    path = kanal(main_root, text=PREAMBLE + OLD_BAD)
    payload = edit(path, "- Durum: ACTIVE", "- Durum: RETIRED")
    assert violations(guard, payload, main_root) == []


def test_duplicate_of_existing_header_is_new(guard, main_root):
    bad = "### B-HOOK2-0009 · 2026-11-16 22:40 · → koordinatör · ACK\n" + P + "\n"
    path = kanal(main_root, text=PREAMBLE + bad)
    found = violations(guard, write(path, PREAMBLE + bad + bad), main_root)
    assert len(found) == 1


def test_header_in_code_fence_ignored(guard, main_root):
    fenced = OK_MSG + "```\n### <ID> · <YYYY-MM-DD HH:MM> · → <alici> · <TUR>\n```\n"
    assert appended(guard, main_root, fenced) == []


def test_edit_replace_all(guard, main_root):
    path = kanal(main_root, text=PREAMBLE + "X\nX\n")
    payload = edit(path, "X\n", OK_MSG, replace_all=True)
    found = violations(guard, payload, main_root)
    assert found == []


def test_edit_old_string_missing_checks_new_string(guard, main_root):
    path = kanal(main_root)
    bad = msg(H + "YIGIN-AÇ", P)
    found = violations(guard, edit(path, "YOK-BOYLE-METIN", bad), main_root)
    assert found and "tür" in found[0].message


def test_multiedit_checked(guard, main_root):
    path = kanal(main_root)
    bad = msg(H + "BILINMEYEN", P)
    payload = multiedit(path, [("- Durum: ACTIVE", "- Durum: ACTIVE"), ("## Mesajlar\n", "## Mesajlar\n" + bad)])
    found = violations(guard, payload, main_root)
    assert found and "tür" in found[0].message


def test_new_channel_file_checked(guard, main_root):
    path = main_root / "state" / "kanal" / "isci-d.md"
    found = violations(guard, write(path, PREAMBLE + msg(H + "YIGIN-AÇ", P)), main_root, rol="isci-d")
    assert found


# --- scope ----------------------------------------------------------------------


def test_archive_not_checked(guard, main_root):
    path = main_root / "state" / "kanal" / "arsiv" / "isci-b-09.md"
    path.parent.mkdir(parents=True)
    payload = write(path, msg(H + "YIGIN-AÇ", P))
    assert violations(guard, payload, main_root, rol="koordinator") == []


def test_other_markdown_not_checked(guard, main_root):
    path = main_root / "state" / "pr" / "fix-x.md"
    assert violations(guard, write(path, msg(H + "YIGIN-AÇ", P)), main_root) == []


def test_hook_process_reports_rule(main_root):
    path = kanal(main_root)
    proc = run_hook(write(path, PREAMBLE + msg(H + "YIGIN-AÇ", P)), main_root, FFCORE_ROL="isci-b")
    assert proc.returncode == 2, proc.stderr
    assert "[KANAL-BICIM]" in proc.stderr
    assert "B-HOOK2-0009" in proc.stderr
    log = (main_root / "state" / "evidence" / "hook-guard.log").read_text(encoding="utf-8")
    assert "KANAL-BICIM" in log and "gövde" not in log


def test_hook_process_valid_allowed(main_root):
    path = kanal(main_root)
    proc = run_hook(write(path, PREAMBLE + OK_MSG), main_root, FFCORE_ROL="isci-b")
    assert proc.returncode == 0 and "FFCORE-GUARD [" not in proc.stderr, proc.stderr


# --- drift: guard lists == protocol --------------------------------------------


def protocol_section() -> str:
    text = PROTOCOL.read_text(encoding="utf-8")
    start = text.index("**Mesaj biçimi")
    end = text.index("**Teslim", start)
    return text[start:end]


def bullet(section: str, label: str) -> str:
    line = next(ln for ln in section.splitlines() if ln.startswith(f"- **{label}"))
    return line.split(":**", 1)[1]


def ticks(text: str) -> list[str]:
    return re.findall(r"`([^`]+)`", text)


def test_types_match_protocol(guard):
    assert tuple(ticks(bullet(protocol_section(), "Tür listesi"))) == guard.MESSAGE_TYPES


def test_recipients_match_protocol(guard):
    line = bullet(protocol_section(), "Alıcı listesi")
    common, coordinator_only = line.split(";", 1)
    assert tuple(ticks(common)) == guard.RECIPIENTS
    assert tuple(ticks(coordinator_only)) == guard.COORDINATOR_ONLY_RECIPIENTS


def test_required_fields_match_protocol(guard):
    rows = [ln for ln in protocol_section().splitlines() if ln.startswith("| ") and "`" in ln]
    common: tuple[str, ...] = ()
    per_type: dict[str, tuple[str, ...]] = {}
    values: dict[str, tuple[str, ...]] = {}
    for row in rows:
        toks = ticks(row)
        fields = [t for t in toks if ":" in t]
        types = [t for t in toks if ":" not in t]
        names = tuple(f.split(":", 1)[0] for f in fields)
        for f in fields:
            name, val = (s.strip() for s in f.split(":", 1))
            if not val.startswith("<"):
                values[name] = tuple(val.split("|"))
        if not types:
            common = names
        for t in types:
            per_type[t] = names
    assert common == guard.COMMON_FIELDS
    assert per_type == guard.TYPE_FIELDS
    assert values == guard.FIELD_VALUES
