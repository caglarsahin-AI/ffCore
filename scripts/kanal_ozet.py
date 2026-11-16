"""Channel summary for the coordinator and the wave report (FOLLOWUP-189 b).

Reads state/kanal/*.md and state/kanal/arsiv/*.md under the main checkout and prints:
- binding messages (GOREV, GOREV-EK, DUZELT, REVIEW-ISTEK, KARAR-GEREK) that no ACK
  answers yet (an ACK answers every ID in its `Cevap` field); those the recipient's channel
  already answered with another message (`Cevap` names the ID) are listed apart as
  "ACK'siz cevaplanmış" (K-HOOK2-0007 MINOR-3),
- per package: WORK_QUEUE state, the last DURUM/PR-HAZIR/REVIEW-SONUC/MERGED message,
  the SHA of the last REVIEW-SONUC with `Sonuc: ONAY`,
- how many headers do not follow the message format ("biçim dışı"; old messages are
  never rewritten, so this is a count, not an error).

The header/field parser is the PreToolUse guard's own (`.claude/hooks/ffcore_guard.py`),
so "biçim dışı" means exactly what the KANAL-BICIM rule would reject.

Usage: python -X utf8 scripts/kanal_ozet.py [--json] [--root <main checkout>]
Stdlib only; reads files, writes nothing.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GUARD_PATH = REPO / ".claude" / "hooks" / "ffcore_guard.py"
BINDING = frozenset({"GOREV", "GOREV-EK", "DUZELT", "REVIEW-ISTEK", "KARAR-GEREK"})
STATE_TYPES = frozenset({"DURUM", "PR-HAZIR", "REVIEW-SONUC", "MERGED"})


def load_guard():
    spec = importlib.util.spec_from_file_location("ffcore_guard", GUARD_PATH)
    if spec is None or spec.loader is None:
        raise SystemExit(f"guard bulunamadı: {GUARD_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def default_root() -> Path:
    """Main checkout; a worktree copy of state/ is never read (MULTI_AGENT_PROTOCOL)."""
    if ".worktrees" in REPO.parts:
        return Path(*REPO.parts[: REPO.parts.index(".worktrees")])
    return REPO


def channel_role(path: Path, known: frozenset[str]) -> str:
    """`isci-b.md` → isci-b; archive `isci-b-09.md` → isci-b (longest known prefix)."""
    stem = path.stem
    matches = [r for r in known if stem == r or stem.startswith(r + "-")]
    return max(matches, key=len) if matches else stem


def read_messages(root: Path, guard) -> tuple[list[dict], int]:
    kanal = root / "state" / "kanal"
    if not kanal.is_dir():
        raise FileNotFoundError(f"state/kanal yok: {kanal}")
    files = sorted(kanal.glob("*.md")) + sorted((kanal / "arsiv").glob("*.md"))
    messages: list[dict] = []
    bad = 0
    for order, path in enumerate(files):
        text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        lines = text.split("\n")
        role = channel_role(path, guard.KNOWN_ROLES)
        for i, header in guard.header_lines(text):
            second = lines[i + 1] if i + 1 < len(lines) else ""
            msg, problems = guard.parse_message(header, second, role)
            if problems or msg is None:
                bad += 1
                continue
            msg["kaynak"] = path.relative_to(root).as_posix()
            msg["sira"] = (msg["ts"], order, i)
            messages.append(msg)
    return messages, bad


def work_queue(root: Path) -> dict[str, str]:
    """Package → state from every `| Paket | Durum | …` table in state/WORK_QUEUE.md."""
    path = root / "state" / "WORK_QUEUE.md"
    if not path.exists():
        return {}
    states: dict[str, str] = {}
    in_table = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            in_table = False
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells[:2] == ["Paket", "Durum"]:
            in_table = True
        elif in_table and len(cells) >= 2 and not set(cells[0]) <= set("-: "):
            states[cells[0].strip("`")] = cells[1]
    return states


def cited(message: dict) -> list[str]:
    value = message["fields"]["Cevap"]
    return [] if value == "-" else [x.strip() for x in value.split(",")]


def answered(messages: list[dict]) -> tuple[set[str], dict[tuple[str, str], str]]:
    """(IDs answered by an ACK, {(channel, ID): first other message citing it})."""
    acked: set[str] = set()
    replies: dict[tuple[str, str], str] = {}
    for m in messages:
        for ref in cited(m):
            if m["tur"] == "ACK":
                acked.add(ref)
            else:
                replies.setdefault((m["kanal"], ref), m["id"])
    return acked, replies


def reply_without_ack(m: dict, replies: dict[tuple[str, str], str]) -> str | None:
    """ID of a reply from the recipient's channel (any channel for `tumu`), else None."""
    if m["to"] == "tumu":
        return next((rid for (_, ref), rid in replies.items() if ref == m["id"]), None)
    return replies.get((m["to"], m["id"]))


def summarize(root: Path) -> dict:
    guard = load_guard()
    messages, bad = read_messages(root, guard)
    messages.sort(key=lambda m: m["sira"])
    acked, replies = answered(messages)
    pending: list[dict] = []
    without_ack: list[dict] = []
    for m in messages:
        if m["tur"] not in BINDING or m["id"] in acked:
            continue
        item = {
            "id": m["id"],
            "tarih": m["ts"],
            "kaynak": m["kaynak"],
            "alici": m["to"],
            "tur": m["tur"],
            "paket": m["fields"]["Paket"],
        }
        reply = reply_without_ack(m, replies)
        if reply is None:
            pending.append(item)
        else:
            without_ack.append({**item, "cevap_id": reply})
    packages: dict[str, dict] = {
        name: {"work_queue": state, "son_durum": None, "son_onay_sha": None}
        for name, state in work_queue(root).items()
    }
    for m in messages:
        pkg = m["fields"]["Paket"]
        if pkg == "-":
            continue
        info = packages.setdefault(
            pkg, {"work_queue": None, "son_durum": None, "son_onay_sha": None}
        )
        if m["tur"] in STATE_TYPES:
            last = {"id": m["id"], "tur": m["tur"], "tarih": m["ts"]}
            for name in ("Durum", "SHA", "Sonuc"):
                if name in m["fields"]:
                    last[name.lower()] = m["fields"][name]
            info["son_durum"] = last
        if m["tur"] == "REVIEW-SONUC" and m["fields"].get("Sonuc") == "ONAY":
            info["son_onay_sha"] = m["fields"]["SHA"]
    return {
        "kok": root.as_posix(),
        "mesaj": len(messages),
        "bicim_disi": bad,
        "bekleyen_ack": pending,
        "acksiz_cevaplanmis": without_ack,
        "paketler": dict(sorted(packages.items())),
    }


def render(data: dict) -> str:
    out = [f"Kanal özeti ({data['kok']}): {data['mesaj']} mesaj, biçim dışı: {data['bicim_disi']}"]
    out.append("")
    out.append(f"ACK bekleyen bağlayıcı mesajlar ({len(data['bekleyen_ack'])}):")
    for p in data["bekleyen_ack"]:
        out.append(f"- {p['id']} · {p['tarih']} · → {p['alici']} · {p['tur']} · {p['paket']}")
    out.append("")
    out.append(
        f"ACK'siz cevaplanmış bağlayıcı mesajlar ({len(data['acksiz_cevaplanmis'])}; "
        "alıcı ACK yazmadı ama cevap verdi):"
    )
    for p in data["acksiz_cevaplanmis"]:
        out.append(f"- {p['id']} · → {p['alici']} · {p['tur']} · {p['paket']} ← {p['cevap_id']}")
    out.append("")
    out.append("Paketler (WORK_QUEUE | son durum mesajı | son ONAY SHA):")
    for name, info in data["paketler"].items():
        last = info["son_durum"]
        last_text = "-"
        if last:
            extra = last.get("durum") or last.get("sonuc") or ""
            last_text = f"{last['id']} {last['tur']} {extra} ({last['tarih']})".replace("  ", " ")
        out.append(
            f"- {name} | {info['work_queue'] or '-'} | {last_text} | {info['son_onay_sha'] or '-'}"
        )
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="JSON çıktı")
    parser.add_argument("--root", type=Path, default=None, help="ana çalışma kopyası")
    args = parser.parse_args(argv)
    root = args.root or default_root()
    try:
        data = summarize(root)
    except FileNotFoundError as exc:
        print(f"kanal_ozet: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(data, ensure_ascii=False, indent=2) if args.json else render(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
