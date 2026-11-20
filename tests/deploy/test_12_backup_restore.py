"""12-2 acceptance 3 (plan/12 7): back up, restore on a fresh stack, everything comes back.

Host test (the tools container has no Docker socket; the scripts drive `docker compose` from
the host). Opt-in and destructive for its own compose project:

    RUN_BACKUP_TESTS=1 FFCORE_VERSION=<tag> BACKEND_PORT=<p> FRONTEND_PORT=<p> \
      FFCORE_TEST_PROJECT=ffcore-12 pytest tests/deploy/test_12_backup_restore.py -s

Steps: down -v; up; small data (tests/deploy/backup_seed.py: project, member, models, a
Markdown document indexed with FAKE_EMBED, a published agent, one chat run); backup.sh;
down -v; restore.sh on the fresh stack (counts compared inside the script); the document
file is back byte for byte; a second restore onto the now non-empty stack is refused.
"""

import json
import os
import secrets
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PROJECT = os.environ.get("FFCORE_TEST_PROJECT", "ffcore-12")
COMPOSE = (
    f"docker compose -p {PROJECT} --env-file .env.test"
    " --env-file tests/e2e/scenarios/e2e.env -f compose.yaml"
)

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_BACKUP_TESTS") != "1",
    reason="NOT_RUN: needs RUN_BACKUP_TESTS=1, Docker on the host and its own compose project",
)


def sh(args, *, env, check=True, timeout=1800):
    result = subprocess.run(
        args, cwd=REPO, env=env, capture_output=True, text=True, timeout=timeout
    )
    print(f"$ {' '.join(args)}\n{result.stdout}{result.stderr}")
    if check and result.returncode != 0:
        pytest.fail(f"exit {result.returncode}: {' '.join(args)}")
    return result


def compose(*args, env, check=True):
    return sh(COMPOSE.split() + list(args), env=env, check=check)


@pytest.fixture
def env():
    values = {
        **os.environ,
        "FFCORE_COMPOSE": COMPOSE,
        "COMPOSE_PROFILES": "test",
        # Git Bash on a Windows host rewrites container paths such as /data/storage; the
        # scripts target Linux servers, where this changes nothing.
        "MSYS_NO_PATHCONV": "1",
        "MSYS2_ARG_CONV_EXCL": "*",
        # Per-run credentials for the seed, never written anywhere.
        "E2E_ADMIN_EMAIL": "yedek-admin@example.test",
        "E2E_ADMIN_PASSWORD": secrets.token_urlsafe(18),
        "E2E_PASSWORD": secrets.token_urlsafe(18),
    }
    for name in ("FFCORE_VERSION", "BACKEND_PORT", "FRONTEND_PORT"):
        assert values.get(name), f"{name} is not set (docstring)"
    return values


def test_12_7_backup_then_restore_on_a_fresh_stack(env, tmp_path):
    compose("down", "-v", env=env)
    compose("up", "-d", "--wait", "--pull", "never", env=env)
    seeded = compose(
        "run", "--rm", "--no-deps",
        "-e", "E2E_ADMIN_EMAIL", "-e", "E2E_ADMIN_PASSWORD", "-e", "E2E_PASSWORD",
        "tools", "python", "tests/deploy/backup_seed.py",
        env=env,
    )  # fmt: skip
    data = json.loads(seeded.stdout.strip().splitlines()[-1])

    backup = tmp_path / "backup"
    sh(["bash", "deploy/backup.sh", "--out", str(backup)], env=env)
    counts = json.loads((backup / "counts.json").read_text(encoding="utf-8"))
    print("counts.json:", counts)
    for table in ("projects", "agents", "knowledge_bases", "documents", "runs", "messages"):
        assert counts["tables"][table] >= 1, table
    assert counts["storage_files"] >= 1

    compose("down", "-v", env=env)
    restored = sh(["bash", "deploy/restore.sh", "--from", str(backup)], env=env)
    assert "counts equal" in restored.stdout

    files = compose(
        "exec", "-T", "backend", "sh", "-c", "find /data/storage -type f -exec sha256sum {} +",
        env=env,
    )
    assert data["document_sha256"] in files.stdout

    again = sh(["bash", "deploy/restore.sh", "--from", str(backup)], env=env, check=False)
    assert again.returncode == 1 and "already has" in again.stderr
