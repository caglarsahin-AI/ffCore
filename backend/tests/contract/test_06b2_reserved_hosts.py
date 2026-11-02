"""06b-2 review r1 MINOR-1 (K-06b2-0008, decision A): the platform's own services are never an
external agent's target. RESERVED_HOSTS names every compose service (each is a host name on the
platform network), so a service added to compose without it fails here."""

import re
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


def test_06b2_reserved_hosts_cover_seed_model_servers():
    """Review r2 N1 (K-06b2-0013, C): the seed's default model servers (Ollama, vLLM) are
    reserved even when they are not compose services. A provider row's own host is
    FOLLOWUP-146."""
    seeds = sorted((ROOT / "deploy" / "seed").glob("models.*.yaml"))
    assert seeds
    defaults = {
        m.group(1)
        for path in seeds
        for m in re.finditer(r"\$\{SEED_\w+_BASE_URL:-([^}]+)\}", path.read_text(encoding="utf-8"))
    }
    assert {"http://ollama:11434", "http://vllm:8000"} <= defaults
    hosts = {re.match(r"\w+://([^:/]+)", url).group(1) for url in defaults}
    assert hosts <= RESERVED_HOSTS, sorted(hosts - RESERVED_HOSTS)
