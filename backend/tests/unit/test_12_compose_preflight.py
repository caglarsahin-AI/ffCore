"""12 (FOLLOWUP-35): scripts/compose_preflight.py, the profile and overlay coherence check.

Compose cannot derive COMPOSE_PROFILES or COMPOSE_FILE from DEPLOY_PROFILE, so the two stay
explicit settings and every incoherent combination is a named error with the fix (D4 A).
Pure Python, no Docker, no network.
"""

import importlib.util
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "compose_preflight.py"
spec = importlib.util.spec_from_file_location("compose_preflight", SCRIPT)
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)

BASE = {
    "DEPLOY_PROFILE": "llmaas",
    "INFERENCE_BACKEND": "ollama",
    "COMPOSE_PROFILES": "",
    "COMPOSE_FILE": "",
    "EGRESS_ALLOWLIST": "",
    "OLLAMA_CONTEXT_LENGTH": "",
    # 12-2 (FOLLOWUP-46): llmaas refuses the owner as the application's database user.
    "APP_DB_USER": "ffcore_app",
    "APP_DB_PASSWORD": "dummy-not-secret",
}
OLLAMA_FILES = "compose.yaml:deploy/docker-compose.ollama.yml"
EGRESS_FILES = "compose.yaml:deploy/docker-compose.egress.yml:deploy/docker-compose.tls.yml"


def env(**changes):
    return {**BASE, **changes}


def error_code(values):
    with pytest.raises(preflight.PreflightError) as caught:
        preflight.check(values)
    return caught.value.code, str(caught.value)


def test_12_35_plain_llmaas_passes():
    lines = preflight.check(env())
    assert any("llmaas" in line for line in lines)


def test_12_35_airgap_ollama_coherent_passes():
    lines = preflight.check(
        env(
            DEPLOY_PROFILE="airgap",
            COMPOSE_PROFILES="ollama",
            COMPOSE_FILE=OLLAMA_FILES,
            OLLAMA_CONTEXT_LENGTH="32768",
        )
    )
    assert any("ollama" in line for line in lines)


def test_12_35_profile_without_overlay_is_named_error():
    code, message = error_code(
        env(DEPLOY_PROFILE="airgap", COMPOSE_PROFILES="ollama", OLLAMA_CONTEXT_LENGTH="32768")
    )
    assert code == "profile_overlay_mismatch"
    assert "deploy/docker-compose.ollama.yml" in message and "COMPOSE_FILE" in message


def test_12_35_overlay_without_profile_is_named_error():
    code, message = error_code(env(DEPLOY_PROFILE="airgap", COMPOSE_FILE=OLLAMA_FILES))
    assert code == "profile_overlay_mismatch"
    assert "COMPOSE_PROFILES" in message


@pytest.mark.parametrize(
    "changes",
    [
        {"DEPLOY_PROFILE": "llmaas"},
        {"DEPLOY_PROFILE": "airgap", "INFERENCE_BACKEND": "vllm"},
    ],
)
def test_12_35_ollama_needs_airgap_and_ollama_backend(changes):
    values = env(COMPOSE_PROFILES="ollama", COMPOSE_FILE=OLLAMA_FILES, OLLAMA_CONTEXT_LENGTH="1")
    code, _ = error_code({**values, **changes})
    assert code == "profile_backend_mismatch"


def test_12_35_ollama_needs_context_length():
    code, message = error_code(
        env(DEPLOY_PROFILE="airgap", COMPOSE_PROFILES="ollama", COMPOSE_FILE=OLLAMA_FILES)
    )
    assert code == "ollama_context_length_missing"
    assert "OLLAMA_CONTEXT_LENGTH" in message


def test_12_35_external_ollama_is_reported_not_refused():
    # PayCore M3 runs Ollama on the host: airgap + ollama backend without the profile.
    lines = preflight.check(env(DEPLOY_PROFILE="airgap"))
    assert any("external" in line for line in lines)


def test_12_35_unknown_profile_is_refused():
    code, message = error_code(env(COMPOSE_PROFILES="egres"))
    assert code == "unknown_profile" and "egres" in message


def test_12_35_windows_path_separator_is_understood():
    lines = preflight.check(
        env(
            DEPLOY_PROFILE="airgap",
            COMPOSE_PROFILES="ollama",
            COMPOSE_FILE=OLLAMA_FILES.replace(":", ";"),
            OLLAMA_CONTEXT_LENGTH="32768",
        )
    )
    assert any("ollama" in line for line in lines)


def test_12_egress_coherent_passes():
    lines = preflight.check(
        env(
            COMPOSE_PROFILES="egress,tls",
            COMPOSE_FILE=EGRESS_FILES,
            EGRESS_ALLOWLIST="api.anthropic.com,*.openai.azure.com",
        )
    )
    assert any("egress" in line and "2 hosts" in line for line in lines)


def test_12_egress_needs_allowlist():
    code, _ = error_code(env(COMPOSE_PROFILES="egress,tls", COMPOSE_FILE=EGRESS_FILES))
    assert code == "egress_allowlist_empty"


def test_12_egress_is_llmaas_only():
    code, _ = error_code(
        env(
            DEPLOY_PROFILE="airgap",
            COMPOSE_PROFILES="egress,tls",
            COMPOSE_FILE=EGRESS_FILES,
            EGRESS_ALLOWLIST="api.anthropic.com",
        )
    )
    assert code == "egress_requires_llmaas"


def test_12_egress_needs_tls_ingress():
    # The egress overlay makes the app network internal; ports published there do not reach
    # the host (measured, A-12 notes), so the TLS reverse proxy is the only way in.
    code, message = error_code(
        env(
            COMPOSE_PROFILES="egress",
            COMPOSE_FILE="compose.yaml:deploy/docker-compose.egress.yml",
            EGRESS_ALLOWLIST="api.anthropic.com",
        )
    )
    assert code == "egress_requires_tls" and "tls" in message


def test_12_egress_list_for_the_corporate_firewall():
    lines = preflight.egress_list("api.anthropic.com, *.openai.azure.com")
    assert lines == ["api.anthropic.com 443/tcp", "*.openai.azure.com 443/tcp"]


def test_12_egress_list_refuses_empty_and_malformed():
    with pytest.raises(preflight.PreflightError):
        preflight.egress_list("")
    with pytest.raises(preflight.PreflightError) as caught:
        preflight.egress_list("https://api.anthropic.com/v1")
    assert caught.value.code == "egress_allowlist_invalid"


def test_12_cli_reads_env_file_and_exits_1_on_error(tmp_path):
    env_file = tmp_path / "deploy.env"
    env_file.write_text(
        "# comment\nDEPLOY_PROFILE=airgap\nINFERENCE_BACKEND=ollama\nCOMPOSE_PROFILES=ollama\n"
        "COMPOSE_FILE=compose.yaml\nOLLAMA_CONTEXT_LENGTH=32768\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        ["python", str(SCRIPT), "--env-file", str(env_file)],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/local/bin:/usr/bin:/bin:/opt/venv/bin"},
    )
    assert result.returncode == 1
    assert "profile_overlay_mismatch" in result.stdout


def test_12_cli_egress_list(tmp_path):
    env_file = tmp_path / "deploy.env"
    env_file.write_text("EGRESS_ALLOWLIST=api.anthropic.com\n", encoding="utf-8")  # list only
    result = subprocess.run(
        ["python", str(SCRIPT), "--env-file", str(env_file), "--egress-list"],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/local/bin:/usr/bin:/bin:/opt/venv/bin"},
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "api.anthropic.com 443/tcp"


def test_12_35_comma_path_separator_from_env_example_is_understood():
    # .env.example sets COMPOSE_PATH_SEPARATOR=, so the same line works on every OS.
    lines = preflight.check(
        env(
            DEPLOY_PROFILE="airgap",
            COMPOSE_PROFILES="ollama",
            COMPOSE_PATH_SEPARATOR=",",
            COMPOSE_FILE="compose.yaml,deploy/docker-compose.ollama.yml",
            OLLAMA_CONTEXT_LENGTH="32768",
        )
    )
    assert any("ollama" in line for line in lines)


@pytest.mark.parametrize("ports", ["443 99999", "0", "443 abc"])
def test_12_r2_egress_ports_out_of_range_are_refused(ports):
    # r1 NOTE-1: preflight (and so smoke) checks the proxy's ports, 1-65535.
    code, message = error_code(
        env(
            COMPOSE_PROFILES="egress,tls",
            COMPOSE_FILE=EGRESS_FILES,
            EGRESS_ALLOWLIST="api.anthropic.com",
            EGRESS_ALLOWED_PORTS=ports,
        )
    )
    assert code == "egress_ports_invalid" and "EGRESS_ALLOWED_PORTS" in message


def test_12_r2_egress_list_refuses_out_of_range_ports():
    with pytest.raises(preflight.PreflightError) as caught:
        preflight.egress_list("api.anthropic.com", "443 99999")
    assert caught.value.code == "egress_ports_invalid"


def test_12_r2_absolute_overlay_paths_match():
    # r1 NOTE-4: an overlay is matched by the end of its path, so absolute paths pass.
    lines = preflight.check(
        env(
            COMPOSE_PROFILES="tls",
            COMPOSE_FILE="/opt/ff/compose.yaml:/opt/ff/deploy/docker-compose.tls.yml",
        )
    )
    assert any(line.startswith("tls:") for line in lines)


def test_12_r2_a_similar_file_name_is_not_the_overlay():
    code, _ = error_code(
        env(COMPOSE_PROFILES="tls", COMPOSE_FILE="compose.yaml:deploy/my-docker-compose.tls.yml")
    )
    assert code == "profile_overlay_mismatch"


def test_12_r2_env_file_inline_comment_is_dropped(tmp_path):
    # r1 NOTE-4: compose reads ` #` in an unquoted value as a comment; the preflight does too.
    env_file = tmp_path / "deploy.env"
    env_file.write_text(
        "EGRESS_ALLOWLIST=a.test # provider\nQUOTED='b.test # kept'\nHASH=x#y\n",
        encoding="utf-8",
    )
    values = preflight.read_env_file(env_file)
    assert values["EGRESS_ALLOWLIST"] == "a.test"
    assert values["QUOTED"] == "b.test # kept"
    assert values["HASH"] == "x#y"


VLLM_FILES = "compose.yaml,deploy/docker-compose.vllm.yml"


def test_12_2_vllm_coherent_passes():
    lines = preflight.check(
        env(
            DEPLOY_PROFILE="airgap",
            INFERENCE_BACKEND="vllm",
            COMPOSE_PROFILES="vllm",
            COMPOSE_PATH_SEPARATOR=",",
            COMPOSE_FILE=VLLM_FILES,
        )
    )
    assert any(line.startswith("vllm:") for line in lines)


def test_12_2_vllm_profile_without_overlay_is_refused():
    code, message = error_code(
        env(DEPLOY_PROFILE="airgap", INFERENCE_BACKEND="vllm", COMPOSE_PROFILES="vllm")
    )
    assert code == "profile_overlay_mismatch" and "docker-compose.vllm.yml" in message


def test_12_2_vllm_needs_airgap_and_the_vllm_backend():
    for changes in ({"DEPLOY_PROFILE": "llmaas"}, {"INFERENCE_BACKEND": "ollama"}):
        values = env(
            DEPLOY_PROFILE="airgap",
            INFERENCE_BACKEND="vllm",
            COMPOSE_PROFILES="vllm",
            COMPOSE_PATH_SEPARATOR=",",
            COMPOSE_FILE=VLLM_FILES,
        )
        code, _ = error_code({**values, **changes})
        assert code == "profile_backend_mismatch", changes


def test_12_2_llmaas_refuses_the_owner_as_application_user():
    code, message = error_code(env(APP_DB_PASSWORD=""))
    assert code == "db_role_owner" and "APP_DB_PASSWORD" in message


def test_12_2_app_db_user_must_be_ffcore_app():
    code, _ = error_code(env(APP_DB_USER="someone"))
    assert code == "db_role_invalid"


def test_12_2_airgap_may_run_as_the_owner_but_says_so():
    # The PayCore M3 server (airgap) predates the role; it is named, not refused.
    lines = preflight.check(env(DEPLOY_PROFILE="airgap", APP_DB_USER="", APP_DB_PASSWORD=""))
    assert any("owner" in line for line in lines)


def test_12_2_role_line_names_the_role():
    lines = preflight.check(env())
    assert any(line == "database: application connects as ffcore_app" for line in lines)
