"""12-1: egress forward proxy and TLS reverse proxy overlays (C16), LiteLLM health (FOLLOWUP-82).

Static checks on the compose files and proxy configs; the behaviour is proven by
tests/integration/test_12_egress.py and test_12_tls.py against a running stack.
"""

import re
import subprocess
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[3]
DEPLOY = REPO / "deploy"
EGRESS = DEPLOY / "docker-compose.egress.yml"
TLS = DEPLOY / "docker-compose.tls.yml"
BASE = DEPLOY / "docker-compose.yml"
IMAGES = (DEPLOY / "offline" / "images.txt").read_text(encoding="utf-8")


def load(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_12_egress_overlay_proxy_service():
    doc = load(EGRESS)
    proxy = doc["services"]["egress-proxy"]
    assert proxy["image"] == "${REGISTRY_PREFIX}ubuntu/squid:6.6-24.04_edge"
    assert proxy["profiles"] == ["egress"]
    assert sorted(proxy["networks"]) == ["default", "egress"]
    assert "ports" not in proxy  # internal only
    assert proxy["environment"]["EGRESS_ALLOWLIST"].startswith("${EGRESS_ALLOWLIST:?")


def test_12_egress_overlay_makes_the_app_network_internal():
    networks = load(EGRESS)["networks"]
    assert networks["default"]["internal"] is True
    assert not networks["egress"].get("internal")


def test_12_egress_overlay_sends_litellm_through_the_proxy():
    env = load(EGRESS)["services"]["litellm"]["environment"]
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        assert env[name] == "http://egress-proxy:3128"
    no_proxy = env["NO_PROXY"].split(",")
    assert {"langfuse-web", "postgres", "localhost"} <= set(no_proxy)
    assert env["no_proxy"] == env["NO_PROXY"]
    # No startup fetch of the cost map from GitHub (explicit, not a denied request in the log).
    assert env["LITELLM_LOCAL_MODEL_COST_MAP"] == "True"


def test_12_squid_config_denies_private_targets_and_logs_no_path():
    conf = (DEPLOY / "egress" / "squid.conf").read_text(encoding="utf-8")
    rules = [line.split() for line in conf.splitlines() if line.startswith("http_access")]
    assert rules[-1] == ["http_access", "deny", "all"]
    deny_private = rules.index(["http_access", "deny", "to_private"])
    allow = rules.index(["http_access", "allow", "ffcore_allow"])
    assert deny_private < allow
    private = next(line for line in conf.splitlines() if line.startswith("acl to_private dst"))
    cidrs = private.split()[3:]
    for cidr in (
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "127.0.0.0/8",
        "169.254.0.0/16",
        # r1 NOTE-3: aligned with the backend's ipaddress.is_global (core/egress.py).
        "198.18.0.0/15",
        "240.0.0.0/4",
        "::",
        "::ffff:0:0/96",
    ):
        assert cidr in cidrs, cidr
    logformat = next(line for line in conf.splitlines() if line.startswith("logformat ffcore"))
    assert "%>rd" in logformat and "%ru" not in logformat and "%>ru" not in logformat
    assert "cache deny all" in conf


def run_start(allowlist, ports=None):
    env = {"PATH": "/usr/bin:/bin", "EGRESS_ALLOWLIST": allowlist}
    if ports is not None:
        env["EGRESS_ALLOWED_PORTS"] = ports
    return subprocess.run(
        ["sh", str(DEPLOY / "egress" / "start.sh"), "--print"],
        capture_output=True,
        text=True,
        env=env,
    )


def test_12_squid_start_translates_the_allowlist():
    result = run_start("api.anthropic.com, *.openai.azure.com")
    assert result.returncode == 0, result.stderr
    assert result.stdout.split("\n--- ports ---\n")[0].split() == [
        "api.anthropic.com",
        ".openai.azure.com",
    ]
    assert result.stdout.split("\n--- ports ---\n")[1].split() == ["443"]


@pytest.mark.parametrize(
    "allowlist", ["", " , ", "https://api.anthropic.com", "api.*.com", "a b", "host:443"]
)
def test_12_squid_start_refuses_empty_or_malformed(allowlist):
    result = run_start(allowlist)
    assert result.returncode == 1
    assert "egress" in result.stderr


@pytest.mark.parametrize("ports", ["443 abc", "0", "99999", "443 65536"])
def test_12_squid_start_refuses_malformed_ports(ports):
    # r1 NOTE-1: 1-65535 only.
    result = run_start("api.anthropic.com", ports)
    assert result.returncode == 1
    assert "EGRESS_ALLOWED_PORTS" in result.stderr


def test_12_tls_overlay_service():
    doc = load(TLS)
    proxy = doc["services"]["tls-proxy"]
    assert proxy["image"] == "${REGISTRY_PREFIX}nginx:1.28.0-alpine"
    assert proxy["profiles"] == ["tls"]
    assert sorted(proxy["networks"]) == ["default", "ingress"]
    assert "${TLS_PORT:-443}:8443" in proxy["ports"]
    # The public (Teams) listener is published on localhost unless the operator opts in.
    assert "${TLS_PUBLIC_BIND:-127.0.0.1}:${TLS_PUBLIC_PORT:-8444}:9443" in proxy["ports"]
    cert = next(v for v in proxy["volumes"] if v.endswith(":/etc/nginx/certs:ro"))
    assert cert.startswith("${TLS_CERT_DIR:?")


def _server_blocks(conf):
    blocks, depth, current = [], 0, None
    for line in conf.splitlines():
        stripped = line.strip()
        if stripped.startswith("server {") and depth == 1:
            current = []
        if current is not None:
            current.append(stripped)
        depth += stripped.count("{") - stripped.count("}")
        if current is not None and depth == 1:
            blocks.append("\n".join(current))
            current = None
    return blocks


def test_12_nginx_public_listener_opens_only_the_teams_path():
    conf = (DEPLOY / "tls" / "nginx.conf").read_text(encoding="utf-8")
    public = next(b for b in _server_blocks(conf) if "listen 9443" in b)
    locations = re.findall(r"^location (.+?) \{", public, re.M)
    assert locations == ["= /channels/teams/messages", "/"]
    # r1 MINOR-1: a fixed URI, so nginx sends the normalised path, never the client's raw one.
    teams = public.split("location = /channels/teams/messages {")[1].split("}")[0]
    assert "proxy_pass http://backend:8000/channels/teams/messages;" in teams
    assert "return 404" in public.split("location / {")[1]
    internal = next(b for b in _server_blocks(conf) if "listen 8443" in b)
    assert "proxy_pass http://frontend:3000" in internal
    assert "proxy_pass http://backend:8000" in internal
    assert "Strict-Transport-Security" in internal
    assert "ssl_protocols TLSv1.2 TLSv1.3;" in conf
    assert "server_tokens off;" in conf


def test_12_new_images_are_pinned_in_images_txt():
    for name in ("ubuntu/squid:6.6-24.04_edge", "nginx:1.28.0-alpine"):
        line = next(row for row in IMAGES.splitlines() if row.startswith(name + " "))
        _, digest, image_id, _ = line.split()
        assert re.fullmatch(r"sha256:[0-9a-f]{64}", digest)
        assert re.fullmatch(r"sha256:[0-9a-f]{64}", image_id)


def test_12_every_overlay_image_has_the_registry_prefix_and_a_pin():
    for path in sorted(DEPLOY.glob("docker-compose*.yml")):
        for name, service in load(path).get("services", {}).items():
            image = service.get("image")
            if image is None:
                continue
            assert image.startswith("${REGISTRY_PREFIX}"), (path.name, name)
            assert not image.endswith(":latest"), (path.name, name)


def test_12_82_litellm_healthcheck_detects_a_half_migrated_schema():
    test = load(BASE)["services"]["litellm"]["healthcheck"]["test"]
    command = " ".join(test)
    assert "/health/liveliness" in command
    assert "/key/info" in command and "LITELLM_MASTER_KEY" in command
    assert "500" in command


def test_12_tools_gets_compose_file_for_the_preflight():
    env = load(BASE)["services"]["tools"]["environment"]
    assert env["COMPOSE_FILE"] == "${COMPOSE_FILE:-}"


def test_12_squid_config_says_non_connect_requests_are_allowed():
    # r1 NOTE-2 B: plain requests to allowlisted hosts stay allowed (FOLLOWUP-211); written down.
    conf = (DEPLOY / "egress" / "squid.conf").read_text(encoding="utf-8")
    assert "FOLLOWUP-211" in conf
    assert not any(line.startswith("http_access deny !CONNECT") for line in conf.splitlines())
