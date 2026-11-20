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


def test_env_still_scans_interpreter_body(guard, main_root):
    # MINOR-2 (K-HOOK2-0007): interpreter code stays scanned by ENV
    cmd = "python - <<'EOF'\nprint(open('.env').read())\nEOF"
    assert "ENV" in rules(guard, cmd, main_root)
