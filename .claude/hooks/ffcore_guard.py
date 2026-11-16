"""FFCore PreToolUse guard (Claude Code hook).

Enforces the agent rules that used to live only in text (KARARLAR 16 Nov 2026,
"Ajan kuralları hook ile zorlanır"): no .env, PayCore data boundary, push only by
the coordinator with a per-command flag, PROSES-175 compose flags, three-stack
limit, gate output via tee, single-writer state files, no writes to a worktree's
state/ copy.

Contract: Claude Code passes the tool call as JSON on stdin (tool_name,
tool_input, session_id). Exit 2 blocks the call and stderr goes to the model.
Exit 0 lets it run. FFCORE_GUARD_MODE=warn|block (default block).

This is a safety net, not a sandbox: commands built at runtime (variables,
script files, Makefile recipes, `bash -c` beyond plain text matching) and Bash
writes to state files are not inspected. Stdlib only, no network.
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
GATE_MAKE_TARGETS = frozenset({"lint", "test", "test-int", "smoke"})
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
MAX_FF_STACKS = 3
FF_STACK_RE = re.compile(r"^(ff|review)", re.IGNORECASE)
ENV_RE = re.compile(r"(?<![\w.])\.env(?![.\w])")
PAYCORE_RE = re.compile(r"paycorellm[/\\]+(?:data|eval[/\\]+results)(?:[/\\]|\b)", re.IGNORECASE)
TOP_SPLIT_RE = re.compile(r"&&|\|\||;|\n|(?<![>&|])&(?![>&])")
PIPE_SPLIT_RE = re.compile(r"\|")
LOG_DETAIL_MAX = 120


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


def check_compose(toks: list[str]) -> list[Violation]:
    idx = None
    for i, t in enumerate(toks):
        if basename(t) == "docker-compose":
            idx = i + 1
            break
        if t == "compose" and i > 0 and basename(toks[i - 1]) == "docker":
            idx = i + 1
            break
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


def check_bash(command: str, payload: Mapping, env: Mapping[str, str]) -> list[Violation]:
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
    for segment in TOP_SPLIT_RE.split(command):
        parts = [tokens(p) for p in PIPE_SPLIT_RE.split(segment)]
        has_tee = any(
            strip_assignments(t)[:1] and basename(strip_assignments(t)[0]) == "tee" for t in parts
        )
        for toks in parts:
            if not toks:
                continue
            found.extend(check_push(toks, payload, env))
            found.extend(check_compose(toks))
            if is_gate_command(toks) and not has_tee:
                found.append(
                    Violation(
                        "KAPI",
                        "kapı/test çıktısı tamamen dosyaya: ... 2>&1 | tee "
                        "state/evidence/<paket>-<adım>.log (K-05a-0011)",
                    )
                )
    return found


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
    """('role', name) or ('pr', stem) for single-writer files under the main root."""
    low = rel.lower()
    if low in COORDINATOR_FILES:
        return ("role", "koordinator")
    m = re.match(r"^state/kanal/([^/]+)\.md$", rel, re.IGNORECASE)
    if m:
        return ("role", m.group(1).lower())
    m = re.match(r"^state/pr/([^/]+)\.md$", rel, re.IGNORECASE)
    if m:
        return ("pr", m.group(1))
    if low.startswith("state/reviews/"):
        return ("role", "inceleyici")
    return None


def check_write(path: str, payload: Mapping, env: Mapping[str, str]) -> list[Violation]:
    if not path:
        return []
    if norm(path).rsplit("/", 1)[-1] == ".env":
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
    info = resolve_role(payload, env)
    if info.rol is None:
        return [Violation("TEK-YAZAR", f"{rel}: {no_role_message(info, payload, env)}")]
    kind, name = owner
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


def log_line(
    env: Mapping[str, str], mode: str, role: str, tool: str, rule: str, detail: str
) -> None:
    from datetime import datetime  # lazy: only violations are logged

    detail = re.sub(r"[\r\n\t]+", " ", detail)[:LOG_DETAIL_MAX]
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
