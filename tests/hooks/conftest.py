"""Shared helpers for the FFCore PreToolUse guard tests.

The guard is exercised two ways:
- as a subprocess (the real contract: JSON on stdin -> exit code + stderr), and
- in-process via ``decide()`` where an external probe (``docker compose ls``) must be faked.

Every test runs against a temporary main root (``FFCORE_MAIN_ROOT``) so the real
``state/`` directory is never read or written.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GUARD_PATH = REPO_ROOT / ".claude" / "hooks" / "ffcore_guard.py"
SETTINGS_PATH = REPO_ROOT / ".claude" / "settings.json"

# Inherited variables that would make the tests depend on the calling session.
_SCRUB = (
    "FFCORE_ROL",
    "FFCORE_PAKET",
    "FFCORE_GUARD_MODE",
    "FFCORE_PUSH_OK",
    "FFCORE_MAIN_ROOT",
    "CLAUDE_CODE_HOST_SESSION_ID",
    "CLAUDE_PROJECT_DIR",
)

SESSION_ID = "11111111-2222-3333-4444-555555555555"


@pytest.fixture
def main_root(tmp_path: Path) -> Path:
    root = tmp_path / "ffcore"
    for sub in ("state/kanal", "state/pr", "state/reviews", "state/evidence"):
        (root / sub).mkdir(parents=True)
    return root


def base_env(main_root: Path, **extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in _SCRUB}
    env["FFCORE_MAIN_ROOT"] = str(main_root)
    env.update(extra)
    return env


def bash(command: str, session_id: str = SESSION_ID) -> dict:
    return {
        "session_id": session_id,
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }


def edit(path: str | Path, tool: str = "Edit", session_id: str = SESSION_ID) -> dict:
    key = "notebook_path" if tool == "NotebookEdit" else "file_path"
    tool_input = {key: str(path)}
    if tool == "Write":
        tool_input["content"] = "SECRET-CONTENT-MUST-NOT-BE-LOGGED"
    elif tool in ("Edit", "MultiEdit"):
        tool_input["old_string"] = "a"
        tool_input["new_string"] = "SECRET-CONTENT-MUST-NOT-BE-LOGGED"
    return {
        "session_id": session_id,
        "hook_event_name": "PreToolUse",
        "tool_name": tool,
        "tool_input": tool_input,
    }


def run_hook(
    payload: dict | str, main_root: Path, **env_extra: str
) -> subprocess.CompletedProcess[str]:
    data = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(
        [sys.executable, str(GUARD_PATH)],
        input=data,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=base_env(main_root, **env_extra),
        timeout=30,
    )


def write_registry(main_root: Path, sessions: dict) -> None:
    (main_root / "state" / "oturumlar.json").write_text(
        json.dumps({"sessions": sessions}), encoding="utf-8"
    )


@pytest.fixture
def guard():
    """Import the guard module from its file path (it is not a package)."""
    spec = importlib.util.spec_from_file_location("ffcore_guard", GUARD_PATH)
    assert spec and spec.loader, f"guard not found: {GUARD_PATH}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
