"""06b acceptance 5 (review r1 MINOR-2): an outside client cannot reach LiteLLM. The facade is the
one public entry; LiteLLM publishes no host port in any profile or override file."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
COMPOSE_FILES = sorted((ROOT / "deploy").glob("docker-compose*.yml"))


def _services(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")).get("services") or {}


def test_06b_litellm_not_published():
    base = _services(ROOT / "deploy" / "docker-compose.yml")
    assert "litellm" in base
    # No profile: the service is the same in every profile combination (test, qdrant, tools...).
    assert "profiles" not in base["litellm"]
    assert len(COMPOSE_FILES) >= 2  # the base and the ollama override are both read
    for path in COMPOSE_FILES:
        service = _services(path).get("litellm") or {}
        assert "ports" not in service, path.name
        assert service.get("network_mode") != "host", path.name
