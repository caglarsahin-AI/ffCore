"""FOLLOWUP-214 (R-HKE-0004 NOTE-1/2): shell comments and the `timeout` wrapper.

An apostrophe in a `#` comment (`# don't …`) was read as an open quote, so the commands on the
following lines were never seen by the command rules. `timeout N cmd` was not unwrapped, so
`timeout 600 pytest` ran a gate without tee. `nice`/`nohup` were already unwrapped (regression).
"""

from __future__ import annotations

import pytest
from conftest import base_env, bash


def rules(guard, command: str, main_root, rol: str = "isci-b") -> list[str]:
    return sorted(
        {v.rule for v in guard.decide(bash(command), base_env(main_root, FFCORE_ROL=rol))}
    )


@pytest.mark.parametrize(
    ("cmd", "rule"),
    [
        ("# don't touch this\npytest backend/tests", "KAPI"),
        ("echo hi  # it's fine\ngit push origin x", "PUSH"),
        ("# can't build here\ndocker build .", "PROSES-175"),
        ("cd backend # the worker's tree\nmake test", "KAPI"),
        ("# don't\nsh <<EOF\ngit push\nEOF", "PUSH"),
        ("# it's\ncat > x.txt <<EOF\nbody\nEOF\ngit push", "PUSH"),
        ("(cd x # don't\n git push)", "PUSH"),
    ],
)
def test_214_apostrophe_in_comment_does_not_hide_later_commands(guard, main_root, cmd, rule):
    assert rule in rules(guard, cmd, main_root), cmd


@pytest.mark.parametrize(
    ("cmd", "rule"),
    [
        ("timeout 600 pytest backend/tests", "KAPI"),
        ("timeout 10m make test", "KAPI"),
        ("timeout --foreground 60 make test", "KAPI"),
        ("timeout -s KILL 5 git push", "PUSH"),
        ("timeout -k 5 60 git push", "PUSH"),
        ("timeout --signal=TERM 5 git push", "PUSH"),
        ("env X=1 timeout 5 git push", "PUSH"),
        ("timeout 5m docker compose up -d", "PROSES-175"),
        ("timeout 900 docker compose -p x run --rm tools make test", "KAPI"),
        ("nohup make test", "KAPI"),
        ("nice -n 5 pytest backend/tests", "KAPI"),
    ],
)
def test_214_timeout_nice_nohup_wrappers_are_checked(guard, main_root, cmd, rule):
    assert rule in rules(guard, cmd, main_root), cmd


@pytest.mark.parametrize(
    "cmd",
    [
        "# git push only in a comment",
        "git status  # then git push, later",
        "echo '#x' && git status",
        'echo "it\'s # not a comment" && git status',
        "echo $# ${#a} a#b",
        "git commit -m 'fix #12: don'\"'\"'t'",
        "timeout 600 make test 2>&1 | tee state/evidence/x.log",
        "# don't\nmake test 2>&1 | tee x.log",
        "timeout 5 git status",
    ],
)
def test_214_harmless_forms_allowed(guard, main_root, cmd):
    assert rules(guard, cmd, main_root) == [], cmd
