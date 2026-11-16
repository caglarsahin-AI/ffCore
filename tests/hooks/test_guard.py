"""Tests for .claude/hooks/ffcore_guard.py (fix/ajan-hooklari, K-HOOK-0001/0002).

Each rule has a blocked/allowed pair. Contract under test:
stdin JSON (tool_name, tool_input, session_id) -> exit 2 + stderr message (block),
exit 0 (allowed, or warn mode with a message).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from conftest import (
    SESSION_ID,
    SETTINGS_PATH,
    base_env,
    bash,
    edit,
    run_hook,
    write_registry,
)

BLOCK = 2


def assert_blocked(proc, rule: str) -> None:
    assert proc.returncode == BLOCK, (proc.returncode, proc.stderr)
    assert f"[{rule}]" in proc.stderr, proc.stderr


def assert_allowed(proc) -> None:
    assert proc.returncode == 0, (proc.returncode, proc.stderr)
    assert "FFCORE-GUARD [" not in proc.stderr, proc.stderr


def rules(guard, payload, main_root, **env) -> list[str]:
    return [v.rule for v in guard.decide(payload, base_env(main_root, **env))]


# --- (a) .env ---------------------------------------------------------------


def test_env_cat_blocked(main_root):
    assert_blocked(run_hook(bash("cat .env"), main_root), "ENV")


@pytest.mark.parametrize("cmd", ["grep KEY .env", "echo X >> .env", "cat backend/.env"])
def test_env_variants_blocked(main_root, cmd):
    assert_blocked(run_hook(bash(cmd), main_root), "ENV")


def test_env_test_allowed(main_root):
    assert_allowed(run_hook(bash("cat .env.test"), main_root))


def test_env_example_allowed(main_root):
    assert_allowed(run_hook(bash("cp .env.example /tmp/x"), main_root))


def test_env_file_flag_with_env_test_allowed(guard, main_root, monkeypatch):
    monkeypatch.setattr(guard, "running_ff_stacks", lambda: [])
    cmd = "docker compose --env-file .env.test -p ffcore-x up -d --wait --no-build --pull never"
    assert rules(guard, bash(cmd), main_root) == []


def test_env_write_tool_blocked(main_root):
    assert_blocked(run_hook(edit(main_root / ".env", "Write"), main_root), "ENV")


def test_env_test_write_tool_allowed(main_root):
    assert_allowed(run_hook(edit(main_root / ".env.test", "Write"), main_root))


# --- (a3) PayCore data boundary ---------------------------------------------


def test_paycore_data_bash_blocked(main_root):
    assert_blocked(run_hook(bash("cat /c/ai_paycore/paycoreLLM/data/x.txt"), main_root), "PAYCORE")


def test_paycore_eval_results_blocked(main_root):
    cmd = r"type C:\ai_paycore\paycoreLLM\eval\results\run1.json"
    assert_blocked(run_hook(bash(cmd), main_root), "PAYCORE")


def test_paycore_src_allowed(main_root):
    cmd = "cat /c/ai_paycore/paycoreLLM/src/paycore_llm/api.py"
    assert_allowed(run_hook(bash(cmd), main_root))


# --- (b) push: only koordinator AND flag (K-HOOK-0002) ----------------------


def test_push_coordinator_with_flag_allowed(main_root):
    proc = run_hook(
        bash("FFCORE_PUSH_OK=1 git push origin main"), main_root, FFCORE_ROL="koordinator"
    )
    assert_allowed(proc)


def test_push_coordinator_without_flag_blocked(main_root):
    proc = run_hook(bash("git push origin main"), main_root, FFCORE_ROL="koordinator")
    assert_blocked(proc, "PUSH")


def test_push_worker_with_flag_blocked(main_root):
    proc = run_hook(bash("FFCORE_PUSH_OK=1 git push origin main"), main_root, FFCORE_ROL="isci-a")
    assert_blocked(proc, "PUSH")


def test_push_no_role_with_flag_blocked(main_root):
    assert_blocked(run_hook(bash("FFCORE_PUSH_OK=1 git push"), main_root), "PUSH")


def test_push_flag_in_hook_env_is_not_enough(main_root):
    proc = run_hook(
        bash("git push origin main"), main_root, FFCORE_ROL="koordinator", FFCORE_PUSH_OK="1"
    )
    assert_blocked(proc, "PUSH")


def test_push_git_c_variant_blocked(main_root):
    proc = run_hook(
        bash("git -C /c/ai_paycore/ffcore push origin main"), main_root, FFCORE_ROL="isci-a"
    )
    assert_blocked(proc, "PUSH")


def test_git_status_allowed(main_root):
    assert_allowed(run_hook(bash("git status --short && git log --oneline -3"), main_root))


# --- (c) compose build / up -------------------------------------------------


def test_compose_build_bare_blocked(main_root):
    assert_blocked(run_hook(bash("docker compose build"), main_root), "PROSES-175")


def test_compose_build_with_file_blocked(main_root):
    proc = run_hook(bash("docker compose -f compose.yaml build backend"), main_root)
    assert_blocked(proc, "PROSES-175")


def test_compose_build_pull_false_allowed(main_root):
    proc = run_hook(bash("docker compose -p x build --pull=false backend"), main_root)
    assert_allowed(proc)


def test_compose_up_build_blocked(main_root):
    proc = run_hook(bash("docker compose up -d --build --pull never"), main_root)
    assert_blocked(proc, "PROSES-175")


def test_compose_up_without_pull_never_blocked(main_root):
    assert_blocked(run_hook(bash("docker compose up -d"), main_root), "PROSES-175")


def test_compose_up_pull_missing_blocked(main_root):
    assert_blocked(run_hook(bash("docker compose up -d --pull missing"), main_root), "PROSES-175")


def test_compose_up_pull_never_allowed(guard, main_root, monkeypatch):
    monkeypatch.setattr(guard, "running_ff_stacks", lambda: [])
    cmd = "docker compose -p ffcore-x up -d --wait --no-build --pull never"
    assert rules(guard, bash(cmd), main_root) == []


def test_compose_up_pull_equals_never_allowed(guard, main_root, monkeypatch):
    monkeypatch.setattr(guard, "running_ff_stacks", lambda: [])
    cmd = "docker compose -p ffcore-x up -d --no-build --pull=never"
    assert rules(guard, bash(cmd), main_root) == []


# --- (d) at most three FF stacks --------------------------------------------

UP = "docker compose -p {p} --env-file .env.test up -d --wait --no-build --pull never"


def test_fourth_stack_blocked(guard, main_root, monkeypatch):
    monkeypatch.setattr(guard, "running_ff_stacks", lambda: ["ffmain", "ffcore-10c1", "review10c1"])
    found = guard.decide(bash(UP.format(p="ffcore-hook")), base_env(main_root))
    assert [v.rule for v in found] == ["YIGIN"]
    assert "ffmain" in found[0].message


def test_third_stack_allowed(guard, main_root, monkeypatch):
    monkeypatch.setattr(guard, "running_ff_stacks", lambda: ["ffmain", "ffcore-10c1"])
    assert rules(guard, bash(UP.format(p="ffcore-hook")), main_root) == []


def test_up_into_running_stack_allowed(guard, main_root, monkeypatch):
    monkeypatch.setattr(guard, "running_ff_stacks", lambda: ["ffmain", "ffcore-10c1", "review10c1"])
    assert rules(guard, bash(UP.format(p="ffcore-10c1")), main_root) == []


def test_stack_count_failure_blocks(guard, main_root, monkeypatch):
    def boom():
        raise guard.GuardError("docker compose ls failed: timeout")

    monkeypatch.setattr(guard, "running_ff_stacks", boom)
    found = guard.decide(bash(UP.format(p="ffcore-hook")), base_env(main_root))
    assert [v.rule for v in found] == ["YIGIN"]
    assert "timeout" in found[0].message


def test_stack_parser_counts_only_running_ff(guard):
    raw = json.dumps(
        [
            {"Name": "ffmain", "Status": "running(12)"},
            {"Name": "review10c1", "Status": "running(3)"},
            {"Name": "ffcore-old", "Status": "exited(5)"},
            {"Name": "airflow", "Status": "running(4)"},
        ]
    )
    assert guard.parse_compose_ls(raw) == ["ffmain", "review10c1"]


# --- (e) gate output to file ------------------------------------------------


def test_make_test_without_tee_blocked(main_root):
    assert_blocked(run_hook(bash("make test"), main_root), "KAPI")


def test_make_test_with_tee_allowed(main_root):
    proc = run_hook(bash("make test 2>&1 | tee state/evidence/x.log"), main_root)
    assert_allowed(proc)


def test_make_lint_tail_blocked(main_root):
    assert_blocked(run_hook(bash("make lint | tail -5"), main_root), "KAPI")


@pytest.mark.parametrize("target", ["test-int", "smoke"])
def test_make_gate_targets_blocked(main_root, target):
    assert_blocked(run_hook(bash(f"make {target}"), main_root), "KAPI")


def test_make_other_target_allowed(main_root):
    assert_allowed(run_hook(bash("make help"), main_root))


def test_pytest_without_tee_blocked(main_root):
    assert_blocked(run_hook(bash("py -3.12 -m pytest tests/hooks -q"), main_root), "KAPI")


def test_pytest_with_tee_allowed(main_root):
    cmd = "py -3.12 -m pytest tests/hooks -q 2>&1 | tee state/evidence/hook-tests.log"
    assert_allowed(run_hook(bash(cmd), main_root))


@pytest.mark.parametrize("flag", ["--version", "--help", "--collect-only -q"])
def test_pytest_info_flags_allowed(main_root, flag):
    assert_allowed(run_hook(bash(f"py -3.12 -m pytest {flag}"), main_root))


# --- (f) single writer -------------------------------------------------------


def test_worker_writes_work_queue_blocked(main_root):
    proc = run_hook(edit(main_root / "state" / "WORK_QUEUE.md"), main_root, FFCORE_ROL="isci-a")
    assert_blocked(proc, "TEK-YAZAR")
    assert "koordinator" in proc.stderr


@pytest.mark.parametrize("rel", ["state/BLOCKERS.md", "KARARLAR.md", "state/oturumlar.json"])
def test_worker_writes_coordinator_files_blocked(main_root, rel):
    proc = run_hook(edit(main_root / rel, "Write"), main_root, FFCORE_ROL="isci-b")
    assert_blocked(proc, "TEK-YAZAR")


def test_coordinator_writes_work_queue_allowed(main_root):
    proc = run_hook(
        edit(main_root / "state" / "WORK_QUEUE.md"), main_root, FFCORE_ROL="koordinator"
    )
    assert_allowed(proc)


def test_worker_writes_own_channel_allowed(main_root):
    path = main_root / "state" / "kanal" / "isci-a.md"
    assert_allowed(run_hook(edit(path), main_root, FFCORE_ROL="isci-a"))


def test_worker_writes_other_channel_blocked(main_root):
    path = main_root / "state" / "kanal" / "koordinator.md"
    assert_blocked(run_hook(edit(path), main_root, FFCORE_ROL="isci-a"), "TEK-YAZAR")


def test_worker_writes_own_pr_allowed(main_root):
    path = main_root / "state" / "pr" / "fix-ajan-hooklari.md"
    proc = run_hook(
        edit(path, "Write"), main_root, FFCORE_ROL="isci-a", FFCORE_PAKET="fix/ajan-hooklari"
    )
    assert_allowed(proc)


def test_other_worker_writes_pr_blocked(main_root):
    path = main_root / "state" / "pr" / "fix-ajan-hooklari.md"
    proc = run_hook(edit(path, "Write"), main_root, FFCORE_ROL="isci-c", FFCORE_PAKET="10c-1")
    assert_blocked(proc, "TEK-YAZAR")


def test_worker_without_package_writes_pr_blocked(main_root):
    path = main_root / "state" / "pr" / "fix-ajan-hooklari.md"
    assert_blocked(run_hook(edit(path), main_root, FFCORE_ROL="isci-a"), "TEK-YAZAR")


def test_pr_alias_field_allowed(main_root):
    write_registry(
        main_root,
        {
            SESSION_ID: {
                "rol": "isci-a",
                "paket": "08-tam-1c-b-olcum",
                "pr": "08-tam-1c",
                "acildi": "x",
            }
        },
    )
    path = main_root / "state" / "pr" / "08-tam-1c.md"
    assert_allowed(run_hook(edit(path), main_root))


def test_reviewer_writes_reviews_allowed(main_root):
    path = main_root / "state" / "reviews" / "10c-1-r1.md"
    assert_allowed(run_hook(edit(path, "Write"), main_root, FFCORE_ROL="inceleyici"))


def test_worker_writes_reviews_blocked(main_root):
    path = main_root / "state" / "reviews" / "10c-1-r1.md"
    assert_blocked(run_hook(edit(path, "Write"), main_root, FFCORE_ROL="isci-c"), "TEK-YAZAR")


def test_evidence_free_for_all(main_root):
    path = main_root / "state" / "evidence" / "x.log"
    assert_allowed(run_hook(edit(path, "Write"), main_root, FFCORE_ROL="isci-a"))


def test_backslash_windows_path_normalized(main_root):
    path = str(main_root / "state" / "WORK_QUEUE.md").replace("/", "\\")
    assert_blocked(run_hook(edit(path), main_root, FFCORE_ROL="isci-a"), "TEK-YAZAR")


def test_forward_slash_path_normalized(main_root):
    path = str(main_root / "state" / "WORK_QUEUE.md").replace("\\", "/")
    assert_blocked(run_hook(edit(path), main_root, FFCORE_ROL="isci-a"), "TEK-YAZAR")


@pytest.mark.parametrize("tool", ["Write", "MultiEdit", "NotebookEdit"])
def test_all_write_tools_checked(main_root, tool):
    proc = run_hook(edit(main_root / "state" / "BLOCKERS.md", tool), main_root, FFCORE_ROL="isci-a")
    assert_blocked(proc, "TEK-YAZAR")


# --- (f2) role resolution ----------------------------------------------------


def test_no_role_single_writer_blocked(main_root):
    proc = run_hook(edit(main_root / "state" / "kanal" / "isci-a.md"), main_root)
    assert_blocked(proc, "TEK-YAZAR")
    assert "rol bulunamadı" in proc.stderr


def test_no_role_message_contains_session_id(main_root):
    proc = run_hook(
        edit(main_root / "KARARLAR.md"), main_root, CLAUDE_CODE_HOST_SESSION_ID="local_abc"
    )
    assert SESSION_ID in proc.stderr
    assert "local_abc" in proc.stderr


def test_no_role_non_owned_file_allowed(main_root):
    assert_allowed(run_hook(edit(main_root / "backend" / "app" / "x.py"), main_root))
    assert_allowed(run_hook(edit(main_root / "state" / "evidence" / "x.log"), main_root))


def test_role_from_registry_session_id(main_root):
    write_registry(main_root, {SESSION_ID: {"rol": "koordinator", "acildi": "x"}})
    assert_allowed(run_hook(edit(main_root / "state" / "WORK_QUEUE.md"), main_root))


def test_role_from_registry_host_id(main_root):
    write_registry(main_root, {"local_abc": {"rol": "koordinator", "acildi": "x"}})
    proc = run_hook(
        edit(main_root / "state" / "WORK_QUEUE.md"),
        main_root,
        CLAUDE_CODE_HOST_SESSION_ID="local_abc",
    )
    assert_allowed(proc)


def test_env_role_overrides_registry(main_root):
    write_registry(main_root, {SESSION_ID: {"rol": "koordinator", "acildi": "x"}})
    proc = run_hook(edit(main_root / "state" / "WORK_QUEUE.md"), main_root, FFCORE_ROL="isci-a")
    assert_blocked(proc, "TEK-YAZAR")


def test_registry_corrupt_is_loud(main_root):
    (main_root / "state" / "oturumlar.json").write_text("{not json", encoding="utf-8")
    proc = run_hook(edit(main_root / "state" / "WORK_QUEUE.md"), main_root)
    assert_blocked(proc, "TEK-YAZAR")
    assert "oturumlar.json okunamadı" in proc.stderr


def test_unknown_role_is_no_role(main_root):
    proc = run_hook(edit(main_root / "state" / "WORK_QUEUE.md"), main_root, FFCORE_ROL="admin")
    assert_blocked(proc, "TEK-YAZAR")
    assert "bilinmeyen rol" in proc.stderr


# --- (g) worktree state copy -------------------------------------------------


def make_worktree(main_root: Path, *parts: str) -> Path:
    wt = main_root.joinpath(".worktrees", *parts)
    wt.mkdir(parents=True)
    (wt / ".git").write_text("gitdir: x\n", encoding="utf-8")
    return wt


def test_worktree_state_write_blocked_for_coordinator(main_root):
    wt = make_worktree(main_root, "fix", "ajan-hooklari")
    proc = run_hook(edit(wt / "state" / "pr" / "x.md"), main_root, FFCORE_ROL="koordinator")
    assert_blocked(proc, "STATE-YOL")


def test_review_worktree_state_write_blocked(main_root):
    wt = make_worktree(main_root, "review-10c-1")
    proc = run_hook(
        edit(wt / "state" / "kanal" / "inceleyici.md"), main_root, FFCORE_ROL="inceleyici"
    )
    assert_blocked(proc, "STATE-YOL")


def test_worktree_non_state_write_allowed(main_root):
    wt = make_worktree(main_root, "fix", "ajan-hooklari")
    proc = run_hook(
        edit(wt / ".claude" / "hooks" / "ffcore_guard.py"), main_root, FFCORE_ROL="isci-a"
    )
    assert_allowed(proc)


def test_worktree_nested_state_dir_in_code_allowed(main_root):
    wt = make_worktree(main_root, "feat", "x")
    proc = run_hook(
        edit(wt / "frontend" / "lib" / "state" / "a.ts"), main_root, FFCORE_ROL="isci-c"
    )
    assert_allowed(proc)


def test_worktree_kararlar_worker_blocked(main_root):
    wt = make_worktree(main_root, "fix", "ajan-hooklari")
    proc = run_hook(edit(wt / "KARARLAR.md"), main_root, FFCORE_ROL="isci-a")
    assert_blocked(proc, "TEK-YAZAR")


# --- (h) mode ----------------------------------------------------------------


def test_warn_mode_exit0_with_message(main_root):
    proc = run_hook(bash("make test"), main_root, FFCORE_GUARD_MODE="warn")
    assert proc.returncode == 0
    assert "[KAPI]" in proc.stderr
    out = json.loads(proc.stdout)
    assert "[KAPI]" in out["systemMessage"]
    assert "permissionDecision" not in json.dumps(out)


def test_block_is_default(main_root):
    assert_blocked(run_hook(bash("make test"), main_root), "KAPI")


def test_unknown_mode_blocks_loudly(main_root):
    proc = run_hook(bash("make test"), main_root, FFCORE_GUARD_MODE="soft")
    assert_blocked(proc, "KAPI")
    assert "bilinmeyen FFCORE_GUARD_MODE" in proc.stderr


def test_allowed_call_prints_nothing(main_root):
    proc = run_hook(bash("ls"), main_root, FFCORE_GUARD_MODE="warn")
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""
    assert proc.stderr.strip() == ""


# --- (i) log -----------------------------------------------------------------


def log_lines(main_root: Path) -> list[str]:
    log = main_root / "state" / "evidence" / "hook-guard.log"
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


def test_block_writes_log_line_without_content(main_root):
    run_hook(edit(main_root / "state" / "WORK_QUEUE.md", "Write"), main_root, FFCORE_ROL="isci-a")
    lines = log_lines(main_root)
    assert len(lines) == 1
    fields = lines[0].split("\t")
    assert fields[1:5] == ["block", "isci-a", "Write", "TEK-YAZAR"]
    assert "SECRET-CONTENT" not in lines[0]


def test_warn_writes_log_line(main_root):
    run_hook(bash("make test"), main_root, FFCORE_GUARD_MODE="warn")
    lines = log_lines(main_root)
    assert len(lines) == 1
    assert lines[0].split("\t")[1:5] == ["warn", "-", "Bash", "KAPI"]


def test_log_truncates_to_120(main_root):
    cmd = "make test && echo " + "x" * 300
    run_hook(bash(cmd), main_root)
    detail = log_lines(main_root)[0].split("\t")[5]
    assert len(detail) == 120


def test_allowed_call_writes_no_log(main_root):
    assert_allowed(run_hook(bash("ls"), main_root))
    assert log_lines(main_root) == []


# --- robustness --------------------------------------------------------------


@pytest.mark.parametrize("tool", ["Read", "Glob", "Grep"])
def test_non_matching_tool_allowed(main_root, tool):
    payload = {"session_id": SESSION_ID, "tool_name": tool, "tool_input": {"file_path": "x"}}
    assert_allowed(run_hook(payload, main_root))


def test_malformed_stdin_blocks_loudly(main_root):
    proc = run_hook("{not json", main_root)
    assert proc.returncode == BLOCK
    assert "FFCORE-GUARD" in proc.stderr


def _explode(*_args, **_kwargs):
    raise RuntimeError("synthetic guard bug")


def test_guard_internal_error_blocks(guard, main_root, monkeypatch, capsys):
    monkeypatch.setattr(guard, "decide", _explode)
    payload = json.dumps(edit(main_root / "backend" / "x.py"))
    assert guard.main(payload, base_env(main_root)) == BLOCK
    assert "synthetic guard bug" in capsys.readouterr().err


@pytest.mark.parametrize(
    "rel", [".claude/hooks/ffcore_guard.py", ".claude/settings.json", ".claude\\hooks\\x.py"]
)
def test_guard_internal_error_never_locks_guard_files(guard, main_root, monkeypatch, capsys, rel):
    """K-HOOK-0003 S9: a broken guard must stay fixable."""
    monkeypatch.setattr(guard, "decide", _explode)
    payload = json.dumps(edit(str(main_root) + "/" + rel, "Write"))
    assert guard.main(payload, base_env(main_root)) == 0
    assert "synthetic guard bug" in capsys.readouterr().err


def test_guard_internal_error_warn_mode_only_warns(guard, main_root, monkeypatch, capsys):
    monkeypatch.setattr(guard, "decide", _explode)
    payload = json.dumps(bash("ls"))
    assert guard.main(payload, base_env(main_root, FFCORE_GUARD_MODE="warn")) == 0
    assert "synthetic guard bug" in capsys.readouterr().err


def test_fast_decide(guard, main_root):
    env = base_env(main_root, FFCORE_ROL="isci-a")
    payload = edit(main_root / "state" / "kanal" / "isci-a.md")
    start = time.perf_counter()
    for _ in range(200):
        guard.decide(payload, env)
    assert (time.perf_counter() - start) / 200 < 0.005


# --- settings.json wiring ----------------------------------------------------


def test_settings_json_valid_and_wires_guard():
    settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    pre = settings["hooks"]["PreToolUse"]
    matchers = {entry["matcher"] for entry in pre}
    assert {"Bash", "Edit|Write|MultiEdit|NotebookEdit"} <= matchers
    for entry in pre:
        commands = [h["command"] for h in entry["hooks"] if h["type"] == "command"]
        assert any("ffcore_guard.py" in c and "CLAUDE_PROJECT_DIR" in c for c in commands)
    deny = settings["permissions"]["deny"]
    assert "Read(**/.env)" in deny and "Edit(**/.env)" in deny
    assert any("paycoreLLM/data/**" in d for d in deny)
    assert any("paycoreLLM/eval/results/**" in d for d in deny)


def test_settings_command_runs_guard(main_root):
    """The exact settings.json command line (no shell) blocks a gate call without tee."""
    import shlex
    import subprocess

    from conftest import REPO_ROOT

    settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    command = settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    argv = shlex.split(command.replace("$CLAUDE_PROJECT_DIR", REPO_ROOT.as_posix()))
    proc = subprocess.run(
        argv,
        input=json.dumps(bash("make test")),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=base_env(main_root),
        timeout=30,
    )
    assert_blocked(proc, "KAPI")


# --- archive (MULTI_AGENT_PROTOCOL "Bağlam bütçesi ve arşiv", 16 Nov 2026) ----


@pytest.mark.parametrize(
    "rel", ["state/arsiv/blockers-kapali.md", "state/kanal/arsiv/isci-a-09.md"]
)
def test_worker_writes_archive_blocked(main_root, rel):
    proc = run_hook(edit(main_root / rel, "Write"), main_root, FFCORE_ROL="isci-a")
    assert_blocked(proc, "TEK-YAZAR")


@pytest.mark.parametrize(
    "rel", ["state/arsiv/blockers-kapali.md", "state/kanal/arsiv/isci-a-09.md"]
)
def test_coordinator_writes_archive_allowed(main_root, rel):
    proc = run_hook(edit(main_root / rel, "Write"), main_root, FFCORE_ROL="koordinator")
    assert_allowed(proc)


def test_coordinator_moves_messages_out_of_worker_channel_allowed(main_root):
    path = main_root / "state" / "kanal" / "isci-a.md"
    assert_allowed(run_hook(edit(path), main_root, FFCORE_ROL="koordinator"))


def test_reviewer_writes_worker_channel_blocked(main_root):
    path = main_root / "state" / "kanal" / "isci-a.md"
    assert_blocked(run_hook(edit(path), main_root, FFCORE_ROL="inceleyici"), "TEK-YAZAR")


# --- r1 fixes (K-HOOK-0006) -----------------------------------------------------

REVIEW_GATE = (
    "docker compose -p review1 --env-file .env.test --profile tools run --rm --no-deps "
    "-e DEPLOY_PROFILE=airgap tools make test"
)


def test_compose_run_gate_without_tee_blocked(guard, main_root):
    """MAJOR-1: the project's real gate form is a compose run, not a host make."""
    assert "KAPI" in rules(guard, bash(REVIEW_GATE), main_root)


def test_compose_run_gate_with_tee_allowed(guard, main_root):
    cmd = REVIEW_GATE + " 2>&1 | tee state/evidence/x.log"
    assert rules(guard, bash(cmd), main_root) == []


def test_compose_run_make_lint_blocked(guard, main_root):
    assert "KAPI" in rules(guard, bash("docker compose run --rm tools make lint"), main_root)


def test_compose_run_make_seed_allowed(guard, main_root):
    assert rules(guard, bash("docker compose run --rm tools make seed"), main_root) == []


def test_compose_exec_pytest_blocked(guard, main_root):
    assert "KAPI" in rules(guard, bash("docker compose exec backend pytest -q"), main_root)


def test_compose_run_value_options_skipped(guard, main_root):
    cmd = "docker compose run --rm -w /app -u root --name x --entrypoint sh tools make smoke"
    assert "KAPI" in rules(guard, bash(cmd), main_root)


def test_compose_run_other_command_allowed(guard, main_root):
    cmd = "docker compose run --rm tools alembic heads"
    assert rules(guard, bash(cmd), main_root) == []


def test_e2e_service_without_tee_blocked(guard, main_root):
    cmd = "docker compose --profile e2e run --rm e2e"
    assert "KAPI" in rules(guard, bash(cmd), main_root)


def test_e2e_service_with_tee_allowed(guard, main_root):
    cmd = "docker compose --profile e2e run --rm e2e 2>&1 | tee state/evidence/e2e.log"
    assert rules(guard, bash(cmd), main_root) == []


def test_make_e2e_without_tee_blocked(guard, main_root):
    assert "KAPI" in rules(guard, bash("docker compose run --rm tools make e2e"), main_root)


@pytest.mark.parametrize("cmd", ["npx playwright test", "pnpm exec playwright test --grep x"])
def test_playwright_test_without_tee_blocked(guard, main_root, cmd):
    assert "KAPI" in rules(guard, bash(cmd), main_root)


def test_playwright_other_command_allowed(guard, main_root):
    assert rules(guard, bash("npx playwright install --dry-run"), main_root) == []


def test_bash_c_push_worker_blocked(guard, main_root):
    """MINOR-2: every rule applies inside sh -c / bash -c."""
    cmd = 'bash -c "git push origin main"'
    assert "PUSH" in rules(guard, bash(cmd), main_root, FFCORE_ROL="isci-a")


def test_sh_c_gate_without_tee_blocked(guard, main_root):
    assert "KAPI" in rules(guard, bash("sh -c 'cd backend && make test'"), main_root)


def test_sh_c_gate_with_outer_tee_allowed(guard, main_root):
    cmd = "sh -c 'make test' 2>&1 | tee state/evidence/x.log"
    assert rules(guard, bash(cmd), main_root) == []


def test_bash_lc_compose_build_blocked(guard, main_root):
    assert "PROSES-175" in rules(guard, bash('bash -lc "docker compose build"'), main_root)


def test_compose_run_sh_c_gate_blocked(guard, main_root):
    cmd = "docker compose run --rm tools sh -c 'make test-int'"
    assert "KAPI" in rules(guard, bash(cmd), main_root)


def test_nested_rule_reported_once(guard, main_root):
    found = rules(guard, bash("bash -c 'cat .env'"), main_root)
    assert found.count("ENV") == 1


@pytest.mark.parametrize(
    ("cmd", "secret", "kept"),
    [
        (
            "git push https://probeuser:ghp_FAKETOKEN0000@github.com/o/r.git main",
            "ghp_FAKETOKEN0000",
            "git push https://",
        ),
        ("OPENAI_API_KEY=sk-FAKE0000 make test", "sk-FAKE0000", "make test"),
        ("make test --db-password=hunter2fake", "hunter2fake", "make test"),
        (
            'curl -H "Authorization: Bearer eyFAKEJWT0000" http://x && make test',
            "eyFAKEJWT0000",
            "curl -H",
        ),
        ("pytest -q --token abc && curl -H 'Bearer eyFAKE0001'", "eyFAKE0001", "pytest -q"),
    ],
)
def test_log_masks_secrets(main_root, cmd, secret, kept):
    """MAJOR-2: hook-guard.log never carries a credential from the command."""
    run_hook(bash(cmd), main_root, FFCORE_ROL="isci-a")
    lines = log_lines(main_root)
    assert lines, "expected a log line"
    for line in lines:
        assert secret not in line
        assert line.split("\t")[4] in {"PUSH", "KAPI"}
    assert any(kept in line.split("\t")[5] for line in lines)
    assert any("***" in line for line in lines)


def test_log_mask_applies_before_truncation(guard):
    cmd = "make test " + "x" * 100 + " API_KEY=" + "s" * 40
    masked = guard.mask_secrets(cmd)
    assert "s" * 10 not in masked and "API_KEY=***" in masked


@pytest.mark.parametrize("cmd", ["cat .ENV", "cat backend/.Env", "echo x >> .ENV"])
def test_env_upper_case_blocked(main_root, cmd):
    """MINOR-1: Windows file names are case-insensitive."""
    assert_blocked(run_hook(bash(cmd), main_root), "ENV")


def test_env_mixed_case_test_file_allowed(main_root):
    assert_allowed(run_hook(bash("cat .Env.Test"), main_root))


def test_env_upper_case_write_tool_blocked(main_root):
    assert_blocked(run_hook(edit(main_root / ".ENV", "Write"), main_root), "ENV")


def test_settings_denies_paycore_env_edit():
    deny = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))["permissions"]["deny"]
    assert "Edit(//c/ai_paycore/paycoreLLM/.env)" in deny


@pytest.mark.parametrize(
    "cmd",
    [
        "make test |& tee state/evidence/x.log",
        'echo "a | b && c" | tee state/evidence/x.log',
        "make test 2>&1 >| out.txt | tee state/evidence/x.log",
    ],
)
def test_splitter_keeps_redirections_and_quotes(guard, main_root, cmd):
    """Quote-aware split (r2): `|&`, `>|` and quoted separators do not break a pipeline."""
    assert rules(guard, bash(cmd), main_root) == []


def test_quoted_separator_does_not_hide_gate(guard, main_root):
    assert "KAPI" in rules(guard, bash("bash -c \"echo 'x;y' && make lint\""), main_root)


# --- r3 (K-HOOK-0010): nesting limit is loud -----------------------------------


def nest(command: str, levels: int) -> str:
    import shlex

    for _ in range(levels):
        command = "sh -c " + shlex.quote(command)
    return command


def test_four_nested_shells_blocked(main_root):
    """r2 MINOR-2 (R13): beyond the nesting limit the guard blocks instead of passing."""
    proc = run_hook(bash(nest("git push origin main", 4)), main_root, FFCORE_ROL="isci-a")
    assert_blocked(proc, "GUARD-DERINLIK")


def test_four_nested_harmless_shells_blocked(guard, main_root):
    assert "GUARD-DERINLIK" in rules(guard, bash(nest("ls", 4)), main_root)


def test_three_nested_shells_still_checked(guard, main_root):
    found = rules(guard, bash(nest("git push origin main", 3)), main_root, FFCORE_ROL="isci-a")
    assert "PUSH" in found and "GUARD-DERINLIK" not in found


def test_three_nested_harmless_shells_allowed(guard, main_root):
    assert rules(guard, bash(nest("ls", 3)), main_root) == []


def test_compose_run_at_nesting_limit_blocked(guard, main_root):
    cmd = nest("docker compose run --rm tools ls", 3)
    assert "GUARD-DERINLIK" in rules(guard, bash(cmd), main_root)


def test_compose_run_without_command_at_limit_allowed(guard, main_root):
    cmd = nest("docker compose run --rm tools", 3)
    assert rules(guard, bash(cmd), main_root) == []
