"""Command wrappers, substitutions and groups (fix/ajan-hooklari-2 D2, FOLLOWUP-189 c).

Review r2 MINOR-1: `env`, `command`, `time`, `bash -o … -c`, `$(…)`, `{ …; }` let a
worker push and an untee'd gate through. Each form has a blocked/allowed pair.
"""

from __future__ import annotations

import pytest
from conftest import base_env, bash


def rules(guard, command: str, main_root, rol: str = "isci-b") -> list[str]:
    return sorted(
        {v.rule for v in guard.decide(bash(command), base_env(main_root, FFCORE_ROL=rol))}
    )


PUSH_FORMS = [
    "env X=1 git push origin x",
    "env -i git push",
    "env -u HOME git push",
    "env -- git push",
    "command git push",
    "command -p git push",
    "time git push",
    "time -p git push",
    "nice git push",
    "nice -n 5 git push",
    "nice -5 git push",
    "nohup git push",
    "exec git push",
    "bash -o pipefail -c 'git push'",
    "bash -euo pipefail -c 'git push'",
    "bash --norc -c 'git push'",
    "sh -e -o errexit -c 'git push'",
    "echo $(git push)",
    'echo "$(git push)"',
    "echo `git push`",
    "x=$(echo $(git push))",
    "{ git push; }",
    "{ git status; git push; } 2>&1",
    "( git push )",
    "(cd backend && git push)",
    "if true; then git push; fi",
    "if git push; then echo ok; fi",
    "for b in a; do git push; done",
    "while false; do git push; done",
    "! git push",
    "env X=1 time nice -n 2 command git push",
]


@pytest.mark.parametrize("cmd", PUSH_FORMS)
def test_worker_push_through_wrapper_blocked(guard, main_root, cmd):
    assert "PUSH" in rules(guard, cmd, main_root), cmd


@pytest.mark.parametrize(
    "cmd",
    [
        "echo '$(git push)'",
        "echo 'git push'",
        "command -v git",
        "command -V git",
        "env",
        "time",
        "git status",
        "echo pushing",
        "{ git status; }",
        "for f in a b; do echo $f; done",
    ],
)
def test_worker_harmless_forms_allowed(guard, main_root, cmd):
    assert rules(guard, cmd, main_root) == [], cmd


@pytest.mark.parametrize(
    "cmd",
    [
        "env FFCORE_PUSH_OK=1 git push origin main",
        "FFCORE_PUSH_OK=1 time git push origin main",
        "{ FFCORE_PUSH_OK=1 git push origin main; }",
    ],
)
def test_coordinator_flagged_push_through_wrapper_allowed(guard, main_root, cmd):
    assert rules(guard, cmd, main_root, rol="koordinator") == [], cmd


def test_coordinator_unflagged_push_in_substitution_blocked(guard, main_root):
    assert "PUSH" in rules(guard, "echo $(git push)", main_root, rol="koordinator")


@pytest.mark.parametrize(
    "cmd",
    [
        "time make test",
        "nice -n 5 pytest -q",
        "env DEPLOY_PROFILE=airgap make test",
        "command make lint",
        "{ make test; }",
        "( make test; make lint )",
        "echo $(make test)",
        "for p in llmaas airgap; do DEPLOY_PROFILE=$p make test; done",
        "if make test; then echo ok; fi",
    ],
)
def test_gate_through_wrapper_without_tee_blocked(guard, main_root, cmd):
    assert "KAPI" in rules(guard, cmd, main_root), cmd


@pytest.mark.parametrize(
    "cmd",
    [
        "time make test 2>&1 | tee state/evidence/x.log",
        "env DEPLOY_PROFILE=airgap make test 2>&1 | tee x.log",
        "{ make test; make lint; } 2>&1 | tee x.log",
        "( make test && make lint ) 2>&1 | tee x.log",
        "nice -n 5 py -3.12 -m pytest tests/hooks -q 2>&1 | time tee x.log",
    ],
)
def test_gate_through_wrapper_with_tee_allowed(guard, main_root, cmd):
    assert rules(guard, cmd, main_root) == [], cmd


@pytest.mark.parametrize(
    "cmd",
    [
        "env docker compose up -d",
        "time docker compose build",
        "{ docker compose up --build; }",
    ],
)
def test_compose_through_wrapper_blocked(guard, main_root, cmd):
    assert "PROSES-175" in rules(guard, cmd, main_root), cmd


def test_substitution_depth_is_loud(guard, main_root):
    cmd = "echo $(echo $(echo $(echo $(git status))))"
    assert "GUARD-DERINLIK" in rules(guard, cmd, main_root)


# --- r2 (K-HOOK2-0007): keywords count only in command position, env -S ------


@pytest.mark.parametrize(
    "cmd",
    [
        "if true; then echo fi; git push origin main; fi",  # W13
        'if grep -q "done" x.txt; then git push origin main; fi',  # W14
        "for x in done; do git push origin main; done",  # W15
        "if echo 'fi'; then git push; fi",
        "while read l; do echo done; git push; done < f",
        "env -S 'git push origin main'",  # W28
        'env -S"git push"',
        "env --split-string='git push'",
    ],
)
def test_r2_push_hidden_in_compound_or_env_s_blocked(guard, main_root, cmd):
    assert "PUSH" in rules(guard, cmd, main_root), cmd


def test_r2_gate_after_quoted_keyword_blocked(guard, main_root):
    cmd = 'if grep -q "build done" log; then make test; fi'
    assert "KAPI" in rules(guard, cmd, main_root)


@pytest.mark.parametrize(
    "cmd",
    [
        'if grep -q "build done" log; then make test; fi 2>&1 | tee x.log',
        "env -S 'git status'",
        "for x in done; do echo $x; done",
    ],
)
def test_r2_harmless_forms_allowed(guard, main_root, cmd):
    assert rules(guard, cmd, main_root) == [], cmd
