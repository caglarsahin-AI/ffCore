"""K-HKE-0002 K1 (A): command rules (KAPI, PROSES-175) read the shell text without data and
interpreter heredoc bodies; a body read by sh/bash stays commands. Before the block switch
the warn log had >= 24 such false positives (state/pr/hook-egress-1.md, log table)."""

from __future__ import annotations

import pytest
from conftest import base_env, bash


def rules(guard, command: str, main_root) -> list[str]:
    return [v.rule for v in guard.decide(bash(command), base_env(main_root, FFCORE_ROL="isci-b"))]


SILENT = [
    # channel message written with cat: the body mentions the gate and a compose command
    "cat >> /c/ai_paycore/ffcore/state/kanal/isci-b.md <<'EOF'\n"
    "### B-X-0001 · 2026-11-20 13:20 · → koordinator · YIGIN-KAPA\n"
    "make test 2>&1 | tail -3\n"
    "docker compose -p ffcore-x build backend\n"
    "EOF",
    # PR note appended with an unquoted delimiter
    "cat >> state/pr/x.md <<EOF\npy -3.12 -m pytest tests/hooks -q\nEOF",
    # tab-stripping heredoc
    "cat <<-EOF > notes.md\n\tmake lint\n\tEOF",
    # document edited by an interpreter: its text is code, not commands
    "python - <<'EOF'\np='docs/x.md'\ns=open(p).read()\nmake test\ndocker build -t x .\nEOF",
    "py -3.12 - <<'PY'\nfrom pathlib import Path\npytest tests\nPY",
    # heredoc followed by a real, tee'd gate
    "cat > f <<'EOF'\nmake test\nEOF\nmake test 2>&1 | tee state/evidence/x.log",
]


@pytest.mark.parametrize("cmd", SILENT)
def test_heredoc_body_text_is_not_a_command(guard, main_root, cmd):
    assert rules(guard, cmd, main_root) == [], cmd


BLOCKED = [
    ("bash <<'EOF'\npy -3.12 -m pytest tests/hooks\nEOF", "KAPI"),
    ("sh <<EOF\nmake test\nEOF", "KAPI"),
    ("bash -s <<'EOF'\nmake lint\nEOF", "KAPI"),
    ("bash <<'EOF'\ndocker compose build\nEOF", "PROSES-175"),
    # a real gate after a data heredoc is still a gate
    ("cat > f <<'EOF'\ntext\nEOF\nmake test", "KAPI"),
    ("cat > f <<'EOF'\ntext\nEOF\npy -3.12 -m pytest tests -q 2>&1 | tail -3", "KAPI"),
    # a gate on the heredoc's own line
    ("make test <<'EOF'\nx\nEOF", "KAPI"),
    ("cat <<'EOF' && docker build .\nx\nEOF", "PROSES-175"),
]


@pytest.mark.parametrize(("cmd", "rule"), BLOCKED)
def test_shell_heredoc_and_real_gates_still_blocked(guard, main_root, cmd, rule):
    assert rule in rules(guard, cmd, main_root), cmd


def test_tee_after_shell_heredoc_satisfies_gate(guard, main_root):
    cmd = "bash <<'EOF' 2>&1 | tee state/evidence/x.log\nmake test\nEOF"
    assert "KAPI" not in rules(guard, cmd, main_root)


# r1 MINOR-2 (K-HKE-0005): the shell behind a wrapper reads the body too; main blocked these.
WRAPPED_SHELL = [
    ("env X=1 bash <<'EOF'\npy -3.12 -m pytest tests\nEOF", "KAPI"),
    ("timeout 600 bash <<'EOF'\npytest tests\nEOF", "KAPI"),
    ("docker compose run --rm -T tools sh <<'EOF'\npytest tests\nEOF", "KAPI"),
    ("docker compose -p x exec -T backend bash <<'EOF'\nmake test\nEOF", "KAPI"),
    ("docker exec -i ffcore-x-backend-1 sh <<'EOF'\npytest tests\nEOF", "KAPI"),
    ("docker compose run --rm tools sh <<'EOF'\ndocker build -t x .\nEOF", "PROSES-175"),
    ("docker compose run --rm -e A=1 -w /work/backend tools bash -s <<'EOF'\npytest\nEOF", "KAPI"),
]


@pytest.mark.parametrize(("cmd", "rule"), WRAPPED_SHELL)
def test_shell_behind_a_wrapper_reads_the_body(guard, main_root, cmd, rule):
    assert rule in rules(guard, cmd, main_root), cmd


WRAPPED_SILENT = [
    # the same wrappers with tee on the heredoc's line
    "docker compose run --rm -T tools sh <<'EOF' 2>&1 | tee state/evidence/x.log\npytest\nEOF",
    "env X=1 bash <<'EOF' 2>&1 | tee x.log\nmake test\nEOF",
    # data readers behind the same wrappers stay data
    "docker compose exec -T postgres psql -U o <<'EOF'\nselect 'make test';\nEOF",
    "docker compose run --rm tools python - <<'EOF'\nprint('pytest tests')\nEOF",
    "docker exec -i c cat > /tmp/x <<'EOF'\nmake test\nEOF",
    "env A=1 python - <<'EOF'\nprint('make test')\nEOF",
]


@pytest.mark.parametrize("cmd", WRAPPED_SILENT)
def test_wrapped_tee_and_data_readers_stay_silent(guard, main_root, cmd):
    assert rules(guard, cmd, main_root) == [], cmd


def test_env_in_interpreter_code_says_why_and_the_way_out(guard, main_root):
    # r1 MINOR-1 A: same match, a message that names the cause and the exit
    cmd = "python - <<'EOF'\ns = 'cp .env.example .env'\nEOF"
    found = guard.decide(bash(cmd), base_env(main_root, FFCORE_ROL="isci-b"))
    messages = [v.message for v in found if v.rule == "ENV"]
    assert messages, found
    assert "yorumlayıcı" in messages[0] and "Write" in messages[0] and "py " in messages[0]


def test_env_path_message_unchanged(guard, main_root):
    found = guard.decide(bash("cat .env"), base_env(main_root, FFCORE_ROL="isci-b"))
    assert [v.message for v in found if v.rule == "ENV"] == [
        ".env okunmaz ve yazılmaz; testler .env.test ile (SECURITY_AND_PERMISSIONS)"
    ]


def test_env_still_scans_interpreter_body(guard, main_root):
    # MINOR-2 (K-HOOK2-0007): interpreter code stays scanned by ENV
    cmd = "python - <<'EOF'\nprint(open('.env').read())\nEOF"
    assert "ENV" in rules(guard, cmd, main_root)
