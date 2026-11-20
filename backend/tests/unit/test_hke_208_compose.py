"""FOLLOWUP-208: the egress overlay gives the backend's own outbound clients the forward proxy.

Static checks; the behaviour is tests/integration/test_12_egress.py (RUN_EGRESS_TESTS=1).
"""

from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[3]
EGRESS = yaml.safe_load((REPO / "deploy" / "docker-compose.egress.yml").read_text("utf-8"))
PROXY_URL = "http://egress-proxy:3128"
# Every service that runs ffcore with SafeOutboundClient for external hosts.
APP_SERVICES = ["backend", "worker", "agent-worker", "agent-worker-bg"]


@pytest.mark.parametrize("service", APP_SERVICES)
def test_hke_208_overlay_sets_the_proxy_for_app_services(service):
    spec = EGRESS["services"][service]
    assert spec["environment"]["EGRESS_PROXY_URL"] == PROXY_URL
    assert spec["depends_on"]["egress-proxy"]["condition"] == "service_healthy"


def test_hke_208_overlay_no_longer_announces_the_known_limit():
    text = (REPO / "deploy" / "docker-compose.egress.yml").read_text("utf-8")
    assert "Known limit (FOLLOWUP-208)" not in text
    assert "EGRESS_PROXY_URL" in text


def test_hke_208_env_example_documents_the_proxy_setting():
    text = (REPO / ".env.example").read_text("utf-8")
    assert "fail with a connection error until FOLLOWUP-208" not in text
    # set by the overlay, not by .env: documented as a comment, never as a variable line
    assert "# EGRESS_PROXY_URL" in text
    assert "\nEGRESS_PROXY_URL=" not in text
