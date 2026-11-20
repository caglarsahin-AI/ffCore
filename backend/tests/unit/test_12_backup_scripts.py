"""12-2 (plan/12 7): deploy/backup.sh and deploy/restore.sh, argument handling and refusals.

The scripts run for real with a stub `docker` first on PATH that records every call and
answers nothing (no daemon, no network). The full prova against a stack is the host test
tests/deploy/test_12_backup_restore.py (RUN_BACKUP_TESTS=1).
"""

import hashlib
import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
BACKUP = REPO / "deploy" / "backup.sh"
RESTORE = REPO / "deploy" / "restore.sh"


@pytest.fixture
def stub(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "calls"
    calls.write_text("", encoding="utf-8")
    docker = bin_dir / "docker"
    docker.write_text(f'#!/usr/bin/env bash\necho "$*" >> {calls}\n', encoding="utf-8")
    docker.chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}
    return env, calls


def run(script, *args, env):
    return subprocess.run(
        ["bash", str(script), *args], capture_output=True, text=True, env=env, cwd=REPO
    )


@pytest.mark.parametrize("script", [BACKUP, RESTORE])
def test_12_7_help(script, stub):
    env, calls = stub
    result = run(script, "--help", env=env)
    assert result.returncode == 0 and "usage:" in result.stdout.lower()
    assert calls.read_text(encoding="utf-8") == ""


@pytest.mark.parametrize("script", [BACKUP, RESTORE])
def test_12_7_unknown_option_and_no_force(script, stub):
    env, _ = stub
    assert run(script, "--force", env=env).returncode == 2
    assert run(script, env=env).returncode == 2  # --out / --from is required


def test_12_7_backup_refuses_a_non_empty_target(stub, tmp_path):
    env, calls = stub
    out = tmp_path / "out"
    out.mkdir()
    (out / "old").write_text("x", encoding="utf-8")
    result = run(BACKUP, "--out", str(out), env=env)
    assert result.returncode == 1 and "not empty" in result.stderr
    assert calls.read_text(encoding="utf-8") == ""


def test_12_7_backup_dry_run_lists_every_step_and_writes_nothing(stub, tmp_path):
    env, calls = stub
    out = tmp_path / "out"
    result = run(BACKUP, "--out", str(out), "--dry-run", "--with-traces", env=env)
    assert result.returncode == 0, result.stderr
    for step in (
        "pg_dump",
        "ffcore.dump",
        "langfuse.dump",
        "knowledge_storage.tar",
        "counts.json",
        "manifest.sha256",
        "langfuse-clickhouse",
        "langfuse-minio",
    ):
        assert step in result.stdout, step
    assert not out.exists()
    assert calls.read_text(encoding="utf-8") == ""


def _backup_dir(tmp_path, tamper=False):
    src = tmp_path / "bk"
    src.mkdir()
    files = {"ffcore.dump": b"a", "langfuse.dump": b"b", "knowledge_storage.tar": b"c"}
    files["counts.json"] = b'{"projects": 0}'
    for name, data in files.items():
        (src / name).write_bytes(data)
    lines = [f"{hashlib.sha256(d).hexdigest()}  {n}" for n, d in files.items()]
    (src / "manifest.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if tamper:
        (src / "ffcore.dump").write_bytes(b"changed")
    return src


def test_12_7_restore_refuses_a_tampered_backup_before_touching_docker(stub, tmp_path):
    env, calls = stub
    result = run(RESTORE, "--from", str(_backup_dir(tmp_path, tamper=True)), env=env)
    assert result.returncode == 1 and "manifest" in result.stderr
    assert calls.read_text(encoding="utf-8") == ""


def test_12_7_restore_refuses_a_directory_without_manifest(stub, tmp_path):
    env, calls = stub
    empty = tmp_path / "empty"
    empty.mkdir()
    result = run(RESTORE, "--from", str(empty), env=env)
    assert result.returncode == 1 and "manifest.sha256" in result.stderr


def test_12_7_restore_dry_run_lists_every_step(stub, tmp_path):
    env, calls = stub
    result = run(RESTORE, "--from", str(_backup_dir(tmp_path)), "--dry-run", env=env)
    assert result.returncode == 0, result.stderr
    for step in ("pg_restore", "fresh", "knowledge_storage.tar", "counts.json", "app-role.sql"):
        assert step in result.stdout, step
    assert calls.read_text(encoding="utf-8") == ""


def test_12_7_restore_is_strict():
    source = RESTORE.read_text(encoding="utf-8")
    assert "--exit-on-error" in source and "--no-owner" in source and "--no-acl" in source
    assert "--force" not in source.replace("no --force", "")
