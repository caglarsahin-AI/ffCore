"""06b-2 review r1 MINOR-1 (K-06b2-0008, decision A): the platform's own services are never an
external agent's target. RESERVED_HOSTS names every compose service (each is a host name on the
platform network), so a service added to compose without it fails here."""

from pathlib import Path

import yaml

from ffcore.services.external_config import BACKEND_CONTAINER_PORT, RESERVED_HOSTS

ROOT = Path(__file__).resolve().parents[3]
COMPOSE_FILES = sorted((ROOT / "deploy").glob("docker-compose*.yml"))


def _services(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")).get("services") or {}


def test_06b2_reserved_hosts_cover_compose():
    assert len(COMPOSE_FILES) >= 2  # the base and the ollama override are both read
    services = {name for path in COMPOSE_FILES for name in _services(path)}
    assert {"litellm", "langfuse-web", "backend", "ollama"} <= services
    assert services <= RESERVED_HOSTS, sorted(services - RESERVED_HOSTS)
    assert "host.docker.internal" in RESERVED_HOSTS  # airgap Ollama on the host (seed)


def test_06b2_backend_container_port_matches_compose():
    ports = _services(ROOT / "deploy" / "docker-compose.yml")["backend"]["ports"]
    assert any(str(p).endswith(f":{BACKEND_CONTAINER_PORT}") for p in ports), ports
