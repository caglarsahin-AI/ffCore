"""FFCore PreToolUse guard (Claude Code hook).

Enforces the agent rules that used to live only in text (KARARLAR 16 Nov 2026,
"Ajan kuralları hook ile zorlanır"): no .env, PayCore data boundary, push only by
the coordinator with a per-command flag, PROSES-175 compose flags, three-stack
limit, gate output via tee, single-writer state files, no writes to a worktree's
state/ copy.

Contract: Claude Code passes the tool call as JSON on stdin (tool_name,
tool_input, session_id). Exit 2 blocks the call and stderr goes to the model.
Exit 0 lets it run. FFCORE_GUARD_MODE=warn|block (default block).

Bash rules also apply inside `sh -c` / `bash -c` text and to the command a
`docker compose run|exec` starts in its service. This is a safety net, not a
sandbox: commands built at runtime (variables, script files, Makefile recipes)
and Bash writes to state files are not inspected. Log lines are masked
(credentials in URLs, *KEY/TOKEN/SECRET/PASS*= values, Authorization/Bearer).
Stdlib only, no network.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from collections.abc import Mapping
from pathlib import Path

KNOWN_ROLES = frozenset(
    {"koordinator", "inceleyici", "isci-a", "isci-b", "isci-c", "isci-d", "test", "sekreter"}
)
WORKER_ROLES = frozenset({"isci-a", "isci-b", "isci-c", "isci-d", "test"})
WRITE_TOOLS = frozenset({"Edit", "Write", "MultiEdit", "NotebookEdit"})
COORDINATOR_FILES = frozenset(
    {"state/work_queue.md", "state/blockers.md", "kararlar.md", "state/oturumlar.json"}
)
GATE_MAKE_TARGETS = frozenset({"lint", "test", "test-int", "smoke", "e2e"})
# compose services whose default command is a gate (KARARLAR r1: e2e is a gate)
GATE_SERVICES = frozenset({"e2e"})
PYTEST_INFO_FLAGS = frozenset({"--version", "--help", "-h", "--collect-only", "--co"})
COMPOSE_VALUE_OPTS = frozenset(
    {
        "-f",
        "--file",
        "-p",
        "--project-name",
        "--env-file",
        "--profile",
        "--project-directory",
        "--ansi",
        "--progress",
        "--parallel",
    }
)
GIT_VALUE_OPTS = frozenset({"-C", "-c", "--git-dir", "--work-tree", "--namespace"})
# `docker compose run|exec` options that take a value (skipped to find the service)
COMPOSE_RUN_VALUE_OPTS = frozenset(
    {
        "-e",
        "--env",
        "--env-from-file",
        "--entrypoint",
        "-w",
        "--workdir",
        "-u",
        "--user",
        "--name",
        "-l",
        "--label",
        "-p",
        "--publish",
        "-v",
        "--volume",
        "--cap-add",
        "--cap-drop",
        "--pull",
        "--index",
    }
)
SHELLS = frozenset({"sh", "bash"})
MAX_NESTING = 3
MAX_FF_STACKS = 3
FF_STACK_RE = re.compile(r"^(ff|review)", re.IGNORECASE)
ENV_RE = re.compile(r"(?<![\w.])\.env(?![.\w])", re.IGNORECASE)  # Windows: .ENV is .env
PAYCORE_RE = re.compile(r"paycorellm[/\\]+(?:data|eval[/\\]+results)(?:[/\\]|\b)", re.IGNORECASE)
LOG_DETAIL_MAX = 120
# Log masking (SECURITY_AND_PERMISSIONS: logs carry no secrets); applied before truncation.
MASKS = (
    (re.compile(r"(\w+://)[^/\s@]+@"), r"\1***@"),
    (
        re.compile(
            r"\b([A-Za-z0-9_-]*(?:key|token|secret|pass(?:word)?|auth|credential)[A-Za-z0-9_-]*)=\S+",
            re.IGNORECASE,
        ),
        r"\1=***",
    ),
    (
        re.compile(r"Authorization:\s*[^\s\"']+(?:\s+[^\s\"']+)?", re.IGNORECASE),
        "Authorization: ***",
    ),
    (re.compile(r"Bearer\s+[^\s\"']+", re.IGNORECASE), "Bearer ***"),
)


# Channel message format (handbook/MULTI_AGENT_PROTOCOL.md "Mesaj biçimi"; single source,
# pinned by tests/hooks/test_kanal_bicim.py drift tests).
MESSAGE_TYPES = (
    "GOREV",
    "GOREV-EK",
    "ACK",
    "SORU",
    "CEVAP",
    "DURUM",
    "KARAR-GEREK",
    "KAYIT-TALEBI",
    "PLAN-ONAY",
    "PR-HAZIR",
    "REVIEW-ISTEK",
    "REVIEW-SONUC",
    "DUZELT",
    "ONAY-TEYIT-ISTEK",
    "ONAY-TEYIT",
    "YIGIN-AC",
    "YIGIN-KAPA",
    "MERGE-BASLIYOR",
    "MERGED",
    "HANDOFF-ISTEK",
    "HANDOFF",
    "RETIRED",
)
RECIPIENTS = (
    "koordinator",
    "inceleyici",
    "isci-a",
    "isci-b",
    "isci-c",
    "isci-d",
    "test",
    "sekreter",
    "tumu",
)
COORDINATOR_ONLY_RECIPIENTS = ("kullanici",)
COMMON_FIELDS = ("Paket", "Cevap")
TYPE_FIELDS = {
    "PR-HAZIR": ("SHA",),
    "REVIEW-ISTEK": ("SHA",),
    "ONAY-TEYIT-ISTEK": ("SHA",),
    "ONAY-TEYIT": ("SHA",),
    "REVIEW-SONUC": ("SHA", "Sonuc", "Bulgu"),
    "DURUM": ("Durum",),
    "YIGIN-AC": ("Yigin",),
    "YIGIN-KAPA": ("Yigin",),
}
FIELD_VALUES = {
    "Sonuc": ("ONAY", "DEGISIKLIK"),
    "Durum": ("PLANNED", "IMPLEMENTED", "VERIFIED", "BLOCKED", "DUYURU"),
}
MESSAGE_ID = r"[A-Z]-[A-Za-z0-9-]+-\d{4}"
FIELD_PATTERNS = {
    "Cevap": re.compile(rf"^(?:-|{MESSAGE_ID}(?:, {MESSAGE_ID})*)$"),
    "SHA": re.compile(r"^[0-9a-f]{40}$"),
    "Bulgu": re.compile(r"^B\d+ M\d+ m\d+ N\d+$"),
}
HEADER_RE = re.compile(r"^### (?P<id>\S+) · (?P<ts>.+?) · → (?P<to>.+?) · (?P<tur>.+?)\s*$")
ID_RE = re.compile(rf"^{MESSAGE_ID}$")
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
SEP = " · "


class GuardError(Exception):
    """An external probe needed by a rule failed (fail-loud: the rule blocks)."""


class Violation:
    """One broken rule (plain class: dataclasses pulls in inspect, slow on startup)."""

    __slots__ = ("rule", "message")

    def __init__(self, rule: str, message: str) -> None:
        self.rule = rule
        self.message = message


class RoleInfo:
    __slots__ = ("rol", "paket", "pr", "problem")

    def __init__(
        self,
        rol: str | None,
        paket: str | None = None,
        pr: str | None = None,
        problem: str | None = None,
    ) -> None:
        self.rol = rol
        self.paket = paket
        self.pr = pr
        self.problem = problem


# --- paths and roles ---------------------------------------------------------


def main_root(env: Mapping[str, str]) -> Path:
    """Main checkout root; state/ always lives here, never in a worktree copy."""
    override = env.get("FFCORE_MAIN_ROOT")
    if override:
        return Path(override)
    here = Path(__file__).resolve()
    if ".worktrees" in here.parts:
        return Path(*here.parts[: here.parts.index(".worktrees")])
    return here.parents[2]


def norm(path: str | Path) -> str:
    """Slash-normalised path; Git Bash /c/... becomes c:/... (case kept)."""
    s = str(path).replace("\\", "/")
    m = re.match(r"^/([a-zA-Z])/(.*)$", s)
    if m:
        s = f"{m.group(1)}:/{m.group(2)}"
    s = re.sub(r"/+", "/", s)
    return s.rstrip("/")


def relative_to_root(path: str, root: Path) -> str | None:
    p, r = norm(path), norm(root)
    if p.lower().startswith(r.lower() + "/"):
        return p[len(r) + 1 :]
    return None


def resolve_role(payload: Mapping, env: Mapping[str, str]) -> RoleInfo:
    rol = env.get("FFCORE_ROL")
    if rol:
        if rol not in KNOWN_ROLES:
            return RoleInfo(None, problem=f"bilinmeyen rol: {rol}")
        return RoleInfo(rol, paket=env.get("FFCORE_PAKET") or None)
    registry = main_root(env) / "state" / "oturumlar.json"
    if not registry.exists():
        return RoleInfo(None, problem="state/oturumlar.json yok")
    try:
        data = json.loads(registry.read_text(encoding="utf-8"))
        sessions = data["sessions"]
        if not isinstance(sessions, dict):
            raise ValueError("'sessions' bir nesne değil")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return RoleInfo(None, problem=f"oturumlar.json okunamadı: {exc}")
    for key in (payload.get("session_id"), env.get("CLAUDE_CODE_HOST_SESSION_ID")):
        if key and key in sessions:
            entry = sessions[key]
            if not isinstance(entry, dict) or not isinstance(entry.get("rol"), str):
                return RoleInfo(None, problem=f"oturumlar.json okunamadı: {key} kaydında 'rol' yok")
            if entry["rol"] not in KNOWN_ROLES:
                return RoleInfo(None, problem=f"bilinmeyen rol: {entry['rol']}")
            return RoleInfo(entry["rol"], paket=entry.get("paket"), pr=entry.get("pr"))
    return RoleInfo(None, problem="kayıt yok")


def no_role_message(info: RoleInfo, payload: Mapping, env: Mapping[str, str]) -> str:
    sid = payload.get("session_id") or "-"
    host = env.get("CLAUDE_CODE_HOST_SESSION_ID") or "-"
    return (
        f"rol bulunamadı ({info.problem}); FFCORE_ROL yok ve state/oturumlar.json'da "
        f"session_id={sid} / host={host} kaydı yok; koordinatöre bu kimliği bildir"
    )


# --- Bash rules -------------------------------------------------------------


def split_pipelines(command: str) -> list[list[str]]:
    """Split on unquoted `&&`, `||`, `;`, newline and `&` into pipelines, each split on
    unquoted `|`. Quotes are respected so `sh -c 'a && b'` stays one element; redirections
    such as `2>&1`, `&>` and `>&` are not separators."""
    pipelines: list[list[str]] = []
    parts: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    i, n = 0, len(command)

    def cut_part() -> None:
        parts.append("".join(buf))
        buf.clear()

    def cut_pipeline() -> None:
        cut_part()
        pipelines.append(parts.copy())
        parts.clear()

    while i < n:
        c = command[i]
        if quote:
            if c == "\\" and quote == '"' and i + 1 < n:
                buf.append(command[i : i + 2])
                i += 2
                continue
            if c == quote:
                quote = None
            buf.append(c)
            i += 1
            continue
        if c in ("'", '"'):
            quote = c
            buf.append(c)
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            buf.append(command[i : i + 2])
            i += 2
            continue
        two = command[i : i + 2]
        if two in ("&&", "||"):
            cut_pipeline()
            i += 2
            continue
        if c in (";", "\n"):
            cut_pipeline()
            i += 1
            continue
        if c == "&":
            prev = command[i - 1] if i else ""
            nxt = command[i + 1] if i + 1 < n else ""
            if prev in (">", "<") or nxt == ">":
                buf.append(c)
            else:
                cut_pipeline()
            i += 1
            continue
        if c == "|":
            if i and command[i - 1] == ">":  # `>|` clobber redirection
                buf.append(c)
            else:
                cut_part()
                if i + 1 < n and command[i + 1] == "&":  # `|&` pipes stderr too
                    i += 1
            i += 1
            continue
        buf.append(c)
        i += 1
    cut_pipeline()
    return pipelines


def tokens(part: str) -> list[str]:
    try:
        toks = shlex.split(part, posix=True)
    except ValueError:
        toks = part.split()
    return [t.lstrip("(").rstrip(")") for t in toks if t.strip("()")]


def basename(token: str) -> str:
    name = token.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return name[:-4] if name.endswith(".exe") else name


def strip_assignments(toks: list[str]) -> list[str]:
    i = 0
    while i < len(toks) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", toks[i]):
        i += 1
    return toks[i:]


def subcommand(toks: list[str], start: int, value_opts: frozenset[str]) -> tuple[int, str | None]:
    i = start
    while i < len(toks):
        t = toks[i]
        if t.startswith("-"):
            i += 2 if (t in value_opts and "=" not in t) else 1
            continue
        return i, t
    return i, None


def compose_project(toks: list[str]) -> str | None:
    for i, t in enumerate(toks):
        if t in ("-p", "--project-name") and i + 1 < len(toks):
            return toks[i + 1]
        if t.startswith(("-p=", "--project-name=")):
            return t.split("=", 1)[1]
    return None


def parse_compose_ls(raw: str) -> list[str]:
    try:
        items = json.loads(raw or "[]")
        return [
            item["Name"]
            for item in items
            if FF_STACK_RE.match(item["Name"]) and str(item["Status"]).startswith("running")
        ]
    except (ValueError, KeyError, TypeError) as exc:
        raise GuardError(f"docker compose ls çıktısı okunamadı: {exc}") from exc


def running_ff_stacks() -> list[str]:
    import subprocess  # lazy: only `compose up` needs it

    try:
        proc = subprocess.run(
            ["docker", "compose", "ls", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise GuardError(f"docker compose ls çalışmadı: {exc}") from exc
    if proc.returncode != 0:
        raise GuardError(f"docker compose ls çıkış {proc.returncode}: {proc.stderr.strip()[:200]}")
    return parse_compose_ls(proc.stdout)


def compose_start(toks: list[str]) -> int | None:
    """Index right after `docker compose` / `docker-compose`, or None."""
    for i, t in enumerate(toks):
        if basename(t) == "docker-compose":
            return i + 1
        if t == "compose" and i > 0 and basename(toks[i - 1]) == "docker":
            return i + 1
    return None


def compose_service_command(toks: list[str]) -> tuple[str, list[str]] | None:
    """(service, command tokens) of `docker compose run|exec`, else None."""
    idx = compose_start(toks)
    if idx is None:
        return None
    pos, sub = subcommand(toks, idx, COMPOSE_VALUE_OPTS)
    if sub not in ("run", "exec"):
        return None
    pos, service = subcommand(toks, pos + 1, COMPOSE_RUN_VALUE_OPTS)
    if service is None:
        return None
    return service, toks[pos + 1 :]


def shell_inner(toks: list[str]) -> str | None:
    """The command text of `sh -c '<text>'` / `bash -lc '<text>'`, else None."""
    rest = strip_assignments(toks)
    if not rest or basename(rest[0]) not in SHELLS:
        return None
    for i in range(1, len(rest) - 1):
        t = rest[i]
        if not t.startswith("-"):
            return None
        if not t.startswith("--") and "c" in t[1:]:
            return rest[i + 1]
    return None


def check_compose(toks: list[str]) -> list[Violation]:
    idx = compose_start(toks)
    if idx is None:
        return []
    _, sub = subcommand(toks, idx, COMPOSE_VALUE_OPTS)
    if sub == "build":
        if "--pull=false" not in toks:
            return [
                Violation(
                    "PROSES-175",
                    "compose build yalnız --pull=false ile (BuildKit base imaj metadata'sı "
                    "için docker.io/ghcr.io'ya bağlanır)",
                )
            ]
        return []
    if sub != "up":
        return []
    if "--build" in toks:
        return [
            Violation(
                "PROSES-175",
                "up --build yok; imaj önce build --pull=false, sonra up --no-build --pull never",
            )
        ]
    pull_never = "--pull=never" in toks or any(
        t == "--pull" and i + 1 < len(toks) and toks[i + 1] == "never" for i, t in enumerate(toks)
    )
    if not pull_never:
        return [
            Violation(
                "PROSES-175",
                "yığın up -d --wait --no-build --pull never ile açılır (ENVIRONMENT_AND_COMMANDS)",
            )
        ]
    try:
        running = running_ff_stacks()
    except GuardError as exc:
        return [
            Violation("YIGIN", f"FF yığınları sayılamadı ({exc}); üç yığın sınırı denetlenemedi")
        ]
    project = compose_project(toks)
    if len(running) >= MAX_FF_STACKS and project not in running:
        return [
            Violation(
                "YIGIN",
                f"aynı anda en çok {MAX_FF_STACKS} FF yığını (açık: {', '.join(running)}); "
                'YIGIN-AÇ sırası koordinatörde (KARARLAR "Üç yığın sınırı")',
            )
        ]
    return []


def is_gate_command(toks: list[str]) -> bool:
    toks = strip_assignments(toks)
    if not toks:
        return False
    head = basename(toks[0])
    if head == "make":
        targets = [t for t in toks[1:] if not t.startswith("-") and "=" not in t]
        return any(t in GATE_MAKE_TARGETS for t in targets)
    if any(
        basename(t) == "playwright" and i + 1 < len(toks) and toks[i + 1] == "test"
        for i, t in enumerate(toks)
    ):
        return True
    is_pytest = head == "pytest" or any(
        t == "-m" and i + 1 < len(toks) and toks[i + 1] == "pytest" for i, t in enumerate(toks)
    )
    return is_pytest and not any(t in PYTEST_INFO_FLAGS for t in toks)


def check_push(toks: list[str], payload: Mapping, env: Mapping[str, str]) -> list[Violation]:
    rest = strip_assignments(toks)
    if not rest or basename(rest[0]) != "git":
        return []
    _, sub = subcommand(rest, 1, GIT_VALUE_OPTS)
    if sub != "push":
        return []
    flag = "FFCORE_PUSH_OK=1" in toks[: len(toks) - len(rest)]
    info = resolve_role(payload, env)
    if info.rol != "koordinator":
        who = info.rol or f"yok: {info.problem}"
        return [
            Violation(
                "PUSH",
                f"git push yalnız koordinatör oturumunda (rolün: {who}); kullanıcının o anki "
                "açık talimatıyla ve komut önekinde FFCORE_PUSH_OK=1 ile (KARARLAR 16 Kasım)",
            )
        ]
    if not flag:
        return [
            Violation(
                "PUSH",
                "komut önekinde FFCORE_PUSH_OK=1 yok; push yalnız kullanıcının o anki açık "
                "talimatıyla: FFCORE_PUSH_OK=1 git push ... (KARARLAR 16 Kasım)",
            )
        ]
    return []


KAPI_MESSAGE = (
    "kapı/test çıktısı tamamen dosyaya: ... 2>&1 | tee "
    "state/evidence/<paket>-<adım>.log (K-05a-0011)"
)


def check_tokens(
    toks: list[str], has_tee: bool, payload: Mapping, env: Mapping[str, str], depth: int
) -> list[Violation]:
    """Rules for one pipeline element, recursing into compose run|exec and sh -c."""
    found = check_push(toks, payload, env) + check_compose(toks)
    if is_gate_command(toks) and not has_tee:
        found.append(Violation("KAPI", KAPI_MESSAGE))
    if depth >= MAX_NESTING:
        service = compose_service_command(toks)
        if shell_inner(toks) is not None or (service is not None and service[1]):
            # fail-loud: an inner command we will not inspect is never let through silently
            found.append(
                Violation(
                    "GUARD-DERINLIK",
                    f"iç içe komut {MAX_NESTING} düzeyi aşıyor; denetlenemedi "
                    "(sh -c / compose run|exec zincirini kısalt)",
                )
            )
        return found
    service = compose_service_command(toks)
    if service is not None:
        name, inner = service
        if not inner and name in GATE_SERVICES and not has_tee:
            found.append(Violation("KAPI", KAPI_MESSAGE))
        if inner:
            found.extend(check_tokens(inner, has_tee, payload, env, depth + 1))
    text = shell_inner(toks)
    if text is not None:
        found.extend(check_bash(text, payload, env, outer_tee=has_tee, depth=depth + 1))
    return found


def check_bash(
    command: str,
    payload: Mapping,
    env: Mapping[str, str],
    outer_tee: bool = False,
    depth: int = 0,
) -> list[Violation]:
    found: list[Violation] = []
    if ENV_RE.search(command):
        found.append(
            Violation(
                "ENV", ".env okunmaz ve yazılmaz; testler .env.test ile (SECURITY_AND_PERMISSIONS)"
            )
        )
    if PAYCORE_RE.search(command):
        found.append(
            Violation(
                "PAYCORE", "paycoreLLM data/** ve eval/results/** okunmaz (CLAUDE.md, PLAN 2d)"
            )
        )
    for pipeline in split_pipelines(command):
        parts = [tokens(p) for p in pipeline]
        has_tee = any(
            strip_assignments(t)[:1] and basename(strip_assignments(t)[0]) == "tee" for t in parts
        )
        for toks in parts:
            if toks:
                found.extend(check_tokens(toks, has_tee or outer_tee, payload, env, depth))
    unique: dict[tuple[str, str], Violation] = {}
    for v in found:
        unique.setdefault((v.rule, v.message), v)
    return list(unique.values())


# --- file-tool rules ---------------------------------------------------------


def worktree_inner(rel: str, root: Path) -> list[str] | None:
    """Path segments inside a worktree, or None if rel is not under .worktrees/."""
    segs = rel.split("/")
    if not segs or segs[0].lower() != ".worktrees":
        return None
    segs = segs[1:]
    for k in range(1, min(3, len(segs)) + 1):
        if root.joinpath(".worktrees", *segs[:k], ".git").exists():
            return segs[k:]
    k = 2 if segs and segs[0].lower() in ("feat", "fix") else 1
    return segs[k:]


def owner_of(rel: str) -> tuple[str, str] | None:
    """('role'|'channel', name) or ('pr', stem) for single-writer files under the main root."""
    low = rel.lower()
    if low in COORDINATOR_FILES or low.startswith(("state/arsiv/", "state/kanal/arsiv/")):
        return ("role", "koordinator")
    m = re.match(r"^state/kanal/([^/]+)\.md$", rel, re.IGNORECASE)
    if m:
        return ("channel", m.group(1).lower())
    m = re.match(r"^state/pr/([^/]+)\.md$", rel, re.IGNORECASE)
    if m:
        return ("pr", m.group(1))
    if low.startswith("state/reviews/"):
        return ("role", "inceleyici")
    return None


def parse_fields(line: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for part in line.split(SEP):
        name, colon, value = part.partition(":")
        if colon and re.match(r"^[A-Za-z]+$", name.strip()):
            fields.setdefault(name.strip(), value.strip())
    return fields


def parse_message(header: str, second: str, channel: str) -> tuple[dict | None, list[str]]:
    """Parse one channel message (header + second line) against the protocol.

    Returns (message, problems); message is None when the header itself is unreadable.
    Shared with scripts/kanal_ozet.py so "biçim dışı" means what the guard rejects.
    """
    m = HEADER_RE.match(header)
    if not m:
        return None, ["başlık '### <ID> · <YYYY-MM-DD HH:MM> · → <alici> · <TUR>' biçiminde değil"]
    msg = {"id": m["id"], "ts": m["ts"], "to": m["to"], "tur": m["tur"], "kanal": channel}
    problems: list[str] = []
    if not ID_RE.match(msg["id"]):
        problems.append(f"ID '{msg['id']}' <harf>-<paket>-<4 hane> değil")
    if not TS_RE.match(msg["ts"]):
        problems.append(f"tarih '{msg['ts']}' YYYY-MM-DD HH:MM değil")
    allowed_to = RECIPIENTS + (COORDINATOR_ONLY_RECIPIENTS if channel == "koordinator" else ())
    if msg["to"] not in allowed_to:
        extra = " (kullanici yalnız koordinatör kanalında)" if msg["to"] == "kullanici" else ""
        problems.append(f"alıcı '{msg['to']}' kapalı listede yok{extra}")
    if msg["tur"] not in MESSAGE_TYPES:
        problems.append(f"tür '{msg['tur']}' kapalı listede yok (açıklama gövdeye)")
    fields = parse_fields(second)
    msg["fields"] = fields
    for name in COMMON_FIELDS + TYPE_FIELDS.get(msg["tur"], ()):
        value = fields.get(name)
        if not value:
            problems.append(f"ikinci satırda {name} alanı yok")
        elif name in FIELD_VALUES and value not in FIELD_VALUES[name]:
            problems.append(f"{name} '{value}' değil: {'|'.join(FIELD_VALUES[name])}")
        elif name in FIELD_PATTERNS and not FIELD_PATTERNS[name].match(value):
            problems.append(f"{name} '{value[:50]}' biçimi yanlış")
    return msg, problems


def header_lines(text: str) -> list[tuple[int, str]]:
    """(index, line) of `### ` headers outside fenced code blocks."""
    out: list[tuple[int, str]] = []
    fenced = False
    for i, line in enumerate(text.split("\n")):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced and line.startswith("### "):
            out.append((i, line))
    return out


def proposed_texts(payload: Mapping, path: Path) -> tuple[str, str]:
    """(old, new) channel text for the write; only the difference is judged."""
    inp = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    old = path.read_text(encoding="utf-8").replace("\r\n", "\n") if path.exists() else ""
    tool = payload.get("tool_name")
    if tool == "Write":
        return old, str(inp.get("content") or "").replace("\r\n", "\n")
    if tool == "Edit":
        edits = [inp]
    elif tool == "MultiEdit":
        edits = [e for e in inp.get("edits") or [] if isinstance(e, dict)]
    else:
        return old, old
    pairs = [
        (
            str(e.get("old_string") or "").replace("\r\n", "\n"),
            str(e.get("new_string") or "").replace("\r\n", "\n"),
            bool(e.get("replace_all")),
        )
        for e in edits
    ]
    cur = old
    for o, n, every in pairs:
        if not o or o not in cur:
            # the tool will fail anyway; judge what the edit adds, never let it pass unread
            return "\n".join(p[0] for p in pairs), "\n".join(p[1] for p in pairs)
        cur = cur.replace(o, n) if every else cur.replace(o, n, 1)
    return old, cur


def check_channel_format(rel: str, channel: str, path: Path, payload: Mapping) -> list[Violation]:
    from collections import Counter

    old, new = proposed_texts(payload, path)
    pending = Counter(line for _, line in header_lines(new))
    pending.subtract(line for _, line in header_lines(old))
    lines = new.split("\n")
    found: list[Violation] = []
    for i, line in header_lines(new):
        if pending[line] <= 0:
            continue
        pending[line] -= 1
        second = lines[i + 1] if i + 1 < len(lines) else ""
        msg, problems = parse_message(line, second, channel)
        if problems:
            who = msg["id"] if msg else line[:40]
            found.append(
                Violation(
                    "KANAL-BICIM",
                    f'{rel} {who}: {"; ".join(problems)} (MULTI_AGENT_PROTOCOL "Mesaj biçimi")',
                )
            )
    return found


def check_write(path: str, payload: Mapping, env: Mapping[str, str]) -> list[Violation]:
    if not path:
        return []
    if norm(path).rsplit("/", 1)[-1].lower() == ".env":
        return [Violation("ENV", ".env okunmaz ve yazılmaz (SECURITY_AND_PERMISSIONS)")]
    root = main_root(env)
    rel = relative_to_root(path, root)
    if rel is None:
        return []
    inner = worktree_inner(rel, root)
    if inner is not None:
        if inner and inner[0].lower() == "state":
            return [
                Violation(
                    "STATE-YOL",
                    f"state/ yalnız {norm(root / 'state')} mutlak yolundan "
                    '(MULTI_AGENT_PROTOCOL "Mutlak yol")',
                )
            ]
        if [s.lower() for s in inner] != ["kararlar.md"]:
            return []
        rel = "KARARLAR.md"
    owner = owner_of(rel)
    if owner is None:
        return []
    kind, name = owner
    fmt = check_channel_format(rel, name, root / rel, payload) if kind == "channel" else []
    info = resolve_role(payload, env)
    if info.rol is None:
        return [Violation("TEK-YAZAR", f"{rel}: {no_role_message(info, payload, env)}")] + fmt
    if kind == "channel":
        # The coordinator moves MERGED-package messages to state/kanal/arsiv/
        # (MULTI_AGENT_PROTOCOL "Bağlam bütçesi ve arşiv"); nobody else writes here.
        if info.rol not in (name, "koordinator"):
            return [Violation("TEK-YAZAR", f"{rel} → {name}; senin rolün {info.rol}")] + fmt
        return fmt
    if kind == "role":
        if info.rol != name:
            return [Violation("TEK-YAZAR", f"{rel} → {name}; senin rolün {info.rol}")]
        return []
    expected = info.pr or (info.paket.replace("/", "-") if info.paket else None)
    if info.rol not in WORKER_ROLES or expected is None or expected.lower() != name.lower():
        return [
            Violation(
                "TEK-YAZAR",
                f"{rel} → paketin işçisi; senin rolün {info.rol}, paketin "
                f"{info.paket or 'bilinmiyor (FFCORE_PAKET ya da oturumlar.json paket)'}",
            )
        ]
    return []


# --- entry points -------------------------------------------------------------


def write_target(payload: Mapping) -> str:
    inp = payload.get("tool_input")
    if not isinstance(inp, dict):
        return ""
    return str(inp.get("file_path") or inp.get("notebook_path") or "")


def decide(payload: Mapping, env: Mapping[str, str]) -> list[Violation]:
    tool = payload.get("tool_name")
    inp = payload.get("tool_input")
    if not isinstance(inp, dict):
        inp = {}
    if tool == "Bash":
        return check_bash(str(inp.get("command") or ""), payload, env)
    if tool in WRITE_TOOLS:
        return check_write(write_target(payload), payload, env)
    return []


def resolve_mode(env: Mapping[str, str]) -> tuple[str, str | None]:
    mode = env.get("FFCORE_GUARD_MODE") or "block"
    if mode in ("warn", "block"):
        return mode, None
    return "block", f"FFCORE-GUARD: bilinmeyen FFCORE_GUARD_MODE={mode}, block uygulandı"


def targets_guard_files(payload: Mapping) -> bool:
    if payload.get("tool_name") not in WRITE_TOOLS:
        return False
    p = "/" + norm(write_target(payload)).lower()
    return "/.claude/hooks/" in p or p.endswith("/.claude/settings.json")


def mask_secrets(text: str) -> str:
    for pattern, repl in MASKS:
        text = pattern.sub(repl, text)
    return text


def log_line(
    env: Mapping[str, str], mode: str, role: str, tool: str, rule: str, detail: str
) -> None:
    from datetime import datetime  # lazy: only violations are logged

    detail = mask_secrets(re.sub(r"[\r\n\t]+", " ", detail))[:LOG_DETAIL_MAX]
    line = "\t".join([datetime.now().isoformat(timespec="seconds"), mode, role, tool, rule, detail])
    log = main_root(env) / "state" / "evidence" / "hook-guard.log"
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "a", encoding="utf-8", newline="") as fh:
            fh.write(line + "\n")
    except OSError as exc:
        print(f"FFCORE-GUARD: kayıt yazılamadı ({log}): {exc}", file=sys.stderr)


def main(stdin_text: str, env: Mapping[str, str]) -> int:
    mode, mode_note = resolve_mode(env)
    if mode_note:
        print(mode_note, file=sys.stderr)
    fail = 0 if mode == "warn" else 2
    try:
        payload = json.loads(stdin_text)
        if not isinstance(payload, dict):
            raise ValueError("girdi bir JSON nesnesi değil")
    except ValueError as exc:
        print(f"FFCORE-GUARD [GUARD-HATA] hook girdisi okunamadı: {exc}", file=sys.stderr)
        log_line(env, mode, "-", "-", "GUARD-HATA", str(exc))
        return fail
    tool = str(payload.get("tool_name") or "-")
    try:
        violations = decide(payload, env)
    except Exception as exc:  # noqa: BLE001 - a guard bug must be loud, not silent
        print(f"FFCORE-GUARD [GUARD-HATA] guard hatası: {exc!r}", file=sys.stderr)
        log_line(env, mode, "-", tool, "GUARD-HATA", repr(exc))
        if targets_guard_files(payload):
            print(
                "FFCORE-GUARD: guard dosyası düzenlemesi serbest (kilitlenme yok)", file=sys.stderr
            )
            return 0
        return fail
    if not violations:
        return 0
    inp = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    detail = str(inp.get("command") or write_target(payload))
    try:
        role = resolve_role(payload, env).rol or "-"
    except Exception:  # noqa: BLE001 - logging must not change the decision
        role = "-"
    lines = [f"FFCORE-GUARD [{v.rule}] {v.message}" for v in violations]
    for v, text in zip(violations, lines, strict=True):
        print(text, file=sys.stderr)
        log_line(env, mode, role, tool, v.rule, detail)
    if mode == "warn":
        print(json.dumps({"systemMessage": "(warn) " + " | ".join(lines)}, ensure_ascii=False))
        return 0
    return 2


def run() -> int:
    """Process entry point.

    .claude/settings.json imports this module instead of running the file as a
    script: an imported module loads from its cached .pyc, which on the Windows
    development machine halves the per-call cost (~1.1 s vs ~2.2 s measured).
    """
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    return main(sys.stdin.read(), os.environ)


if __name__ == "__main__":
    sys.exit(run())
