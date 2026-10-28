"""Package 00 acceptance checks that read repository files (no Docker needed)."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
COMPOSE = ROOT / "deploy" / "docker-compose.yml"
C12_NAMES = (
    "DEPLOY_PROFILE",
    "VECTOR_BACKEND",
    "INFERENCE_BACKEND",
    "OLLAMA_CONTEXT_LENGTH",
    "REGISTRY_PREFIX",
    "OFFLINE",
)


def _compose() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def _env_example() -> dict[str, str]:
    values = {}
    for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def test_00_1_env_example_complete():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    values = _env_example()
    assert values["DEPLOY_PROFILE"] == "llmaas"
    for name in C12_NAMES:
        assert name in values, name
        # every variable carries a Turkish comment on the line(s) above it
        assert re.search(rf"#[^\n]+\n(#[^\n]*\n)*{name}=", text), name
    assert "# DEPLOY_PROFILE=airgap" in text


def test_00_2_registry_prefix_all_images():
    images = [service["image"] for service in _compose()["services"].values() if "image" in service]
    assert images
    for image in images:
        assert image.startswith("${REGISTRY_PREFIX}"), image
        reference = image.removeprefix("${REGISTRY_PREFIX}")
        assert ":" in reference or "@sha256:" in reference, image
        assert not reference.endswith(":latest"), image


def test_00_2_built_images_use_registry_prefix():
    for dockerfile in (ROOT / "backend" / "Dockerfile", ROOT / "frontend" / "Dockerfile"):
        if not dockerfile.exists():
            continue
        for line in dockerfile.read_text(encoding="utf-8").splitlines():
            if line.startswith("FROM ") and " AS " not in line.split("FROM ", 1)[1].split()[0]:
                source = line.split()[1]
                if source.islower() and "/" not in source and ":" not in source:
                    continue  # reference to an earlier stage
                assert source.startswith("${REGISTRY_PREFIX}"), line


def test_00_4_litellm_config_has_no_model_list():
    config = yaml.safe_load(
        (ROOT / "deploy" / "litellm" / "config.yaml").read_text(encoding="utf-8")
    )
    assert "model_list" not in config
    assert "general_settings" in config


def test_00_5_ollama_context_length_required():
    ollama = _compose()["services"]["ollama"]
    assert ollama["profiles"] == ["ollama"]
    env = ollama["environment"]
    assert env["OLLAMA_CONTEXT_LENGTH"].startswith("${OLLAMA_CONTEXT_LENGTH:?")
    assert env["OLLAMA_NUM_PARALLEL"] == "1"
    assert env["OLLAMA_KEEP_ALIVE"] == "-1"


def test_00_6_pull_lists_by_profile():
    ollama_dir = ROOT / "deploy" / "ollama"
    airgap = [
        line
        for line in (ollama_dir / "models.airgap.txt").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    ]
    llmaas = [
        line
        for line in (ollama_dir / "models.llmaas.txt").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    ]
    assert airgap and llmaas == []
    assert "models.${DEPLOY_PROFILE}.txt" in (ollama_dir / "pull.sh").read_text(encoding="utf-8")


def test_00_7_tools_service_has_no_docker_socket():
    tools = _compose()["services"]["tools"]
    assert tools["profiles"] == ["tools"]
    assert not any("docker.sock" in str(volume) for volume in tools.get("volumes", []))


def test_00_1_env_test_fills_every_required_variable_with_marked_dummies():
    env_test = ROOT / ".env.test"
    text = env_test.read_text(encoding="utf-8")
    assert text.startswith("# YALNIZCA GELİŞTİRME/CI")
    values = {}
    for line in text.splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    compose_lines = COMPOSE.read_text(encoding="utf-8").splitlines()
    code = "\n".join(line for line in compose_lines if not line.lstrip().startswith("#"))
    required = set(re.findall(r"\$\{([A-Z0-9_]+):\?", code))
    for name in sorted(required):
        assert values.get(name), name
    secret_names = [n for n in values if re.search(r"PASSWORD|SECRET|SALT|KEY", n)]
    assert secret_names
    for name in secret_names:
        if name == "LANGFUSE_ENCRYPTION_KEY":
            assert values[name] == "0" * 64  # format: 64 hex characters
            continue
        assert "dummy-not-secret" in values[name], name


def test_00_6_airgap_list_has_only_chat_model():
    listed = [
        line
        for line in (ROOT / "deploy" / "ollama" / "models.airgap.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if line and not line.startswith("#")
    ]
    assert listed == ["qwen3.5:35b"]


def test_00_1_http_services_have_healthchecks_for_up_wait():
    # `docker compose up -d --wait` returns only when every service with a healthcheck is
    # healthy; without these, smoke right after `up` fails while LiteLLM/Langfuse start.
    services = _compose()["services"]
    for name, path in (("litellm", "/health/liveliness"), ("langfuse-web", "/api/public/health")):
        test = services[name].get("healthcheck", {}).get("test", [])
        assert path in " ".join(test), name
