"""05a: mcp-search and mcp-sql in compose, and the settings they load.

The relaying services hold no signing key and no backend database access (K-05a-0002 S3):
their environment has neither, and their settings load without them.
"""

from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[3]
SERVICES = ("mcp-search", "mcp-sql")
NEVER = ("OBO_JWT_SECRET", "DATABASE_URL", "FERNET_KEY", "SECRET_KEY", "REDIS_URL")


@pytest.fixture(scope="module")
def compose():
    return yaml.safe_load((REPO / "deploy" / "docker-compose.yml").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", SERVICES)
def test_05a_service_env_has_no_key_or_database(compose, name):
    service = compose["services"][name]
    env = service["environment"]
    assert not any(key in env for key in NEVER), sorted(set(env) & set(NEVER))
    assert "SERVICE_TOKEN" in env and env["ALLOWED_INTERNAL_HOSTS"] == "backend"


@pytest.mark.parametrize("name", SERVICES)
def test_05a_service_default_profile_with_healthcheck(compose, name):
    service = compose["services"][name]
    assert "profiles" not in service  # K-05a-0002 S7: default profile
    assert "healthcheck" in service
    module = name.replace("-", "_") + "_server"
    assert service["command"] == ["python", "-m", f"ffcore.services.{module}"]
    assert "ports" not in service  # internal network only


def test_05a_mcp_sql_reads_demo_database_with_login_user(compose):
    env = compose["services"]["mcp-sql"]["environment"]
    assert "mcp_sql:${AGENT_DEMO_DB_PASSWORD" in env["SQL_DEMO_DATABASE_URL"]
    assert env["SQL_DEMO_DATABASE_URL"].endswith("@postgres:5432/agent_demo")


def test_05a_service_settings_load_without_keys(monkeypatch):
    from ffcore.services.mcp_server_common import McpServiceSettings

    for key in NEVER:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("SERVICE_TOKEN", "dummy-not-secret-service-token-0123456789")
    monkeypatch.setenv("ALLOWED_INTERNAL_HOSTS", "backend")
    monkeypatch.setenv("OFFLINE", "false")
    settings = McpServiceSettings()
    assert settings.allowed_internal_hosts == ["backend"]
    assert not hasattr(settings, "obo_jwt_secret") and not hasattr(settings, "database_url")


def test_05a_backend_reaches_the_services(compose):
    for path in (".env.example", ".env.test"):
        text = (REPO / path).read_text(encoding="utf-8")
        line = next(ln for ln in text.splitlines() if ln.startswith("ALLOWED_INTERNAL_HOSTS="))
        assert {"mcp-search", "mcp-sql"} <= set(line.split("=", 1)[1].split(","))


def _smoke():
    import importlib.util

    spec = importlib.util.spec_from_file_location("smoke05a", REPO / "scripts" / "smoke.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_05a_smoke_checks_both_services(monkeypatch):
    smoke = _smoke()
    seen = []

    def fake(url, payload=None, headers=None):
        seen.append(url)
        return 200, b'{"status": "ok"}'

    monkeypatch.setattr(smoke, "_request", fake)
    assert smoke.check_mcp() == ["mcp-search /healthz 200", "mcp-sql /healthz 200"]
    assert seen == ["http://mcp-search:8000/healthz", "http://mcp-sql:8000/healthz"]
    assert smoke.check_mcp in smoke.CHECKS


def test_05a_smoke_fails_loud(monkeypatch):
    smoke = _smoke()
    monkeypatch.setattr(smoke, "_request", lambda url, payload=None, headers=None: (503, b"{}"))
    with pytest.raises(smoke.SmokeError, match="mcp-search"):
        smoke.check_mcp()


def test_05a_tools_container_can_seed_the_demo_database(compose):
    # `make seed-sql-demo` runs in tools and needs the password (found by the live test).
    assert "AGENT_DEMO_DB_PASSWORD" in compose["services"]["tools"]["environment"]
