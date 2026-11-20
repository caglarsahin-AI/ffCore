"""12-1 acceptance 1: in the egress profile only the forward proxy reaches the outside (C16).

Stack (no real external network; the "outside" is a local network with a documentation
subnet, 198.51.100.0/24, so the proxy's private-address rule is the production one):

    docker compose -p ffcore-12 --env-file .env.test \
      -f compose.yaml -f deploy/docker-compose.egress.yml -f deploy/docker-compose.tls.yml \
      -f backend/tests/compose/egress-tls.test.yml \
      --profile egress --profile tls --profile test up -d --wait --pull never
    docker compose ... run --rm -e RUN_EGRESS_TESTS=1 tools \
      pytest tests/integration/test_12_egress.py

Without RUN_EGRESS_TESTS=1 every test is skipped as NOT_RUN (the overlay is not in the
default test stack).
"""

import os
import socket
import uuid

import httpx2
import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_EGRESS_TESTS") != "1",
    reason="NOT_RUN: needs RUN_EGRESS_TESTS=1 and the egress test stack (module docstring)",
)

PROXY = "http://egress-proxy:3128"
ALLOWED = "http://api.allowed.test:9999"
DENIED = "http://api.denied.test:9999"
REBIND = "http://rebind.test:9999"  # allowlisted, resolves to the internal network
OUTSIDE_IP = "198.51.100.10"  # api.allowed.test's address on the "outside" network
LITELLM = "http://litellm:4000"


def via_proxy(url):
    with httpx2.Client(proxy=PROXY, timeout=10, trust_env=False) as client:
        return client.get(url)


def test_12_e1_allowlisted_host_passes_the_proxy():
    response = via_proxy(f"{ALLOWED}/v1/models")
    assert response.status_code == 200
    assert response.json()["object"] == "list"


def test_12_e1_host_outside_the_allowlist_is_refused():
    assert via_proxy(f"{DENIED}/v1/models").status_code == 403


def test_12_e1_allowlisted_name_on_a_private_address_is_refused():
    assert via_proxy(f"{REBIND}/v1/models").status_code == 403


def test_12_e1_no_direct_way_out_without_the_proxy():
    # The app network is internal: a direct connection to an outside address never completes.
    with pytest.raises(OSError):
        socket.create_connection((OUTSIDE_IP, 9999), timeout=3).close()


def test_12_e1_outside_names_do_not_resolve_on_the_app_network():
    with pytest.raises(socket.gaierror):
        socket.getaddrinfo("api.allowed.test", 9999)


def _headers():
    return {"Authorization": f"Bearer {os.environ['LITELLM_MASTER_KEY']}"}


@pytest.fixture
def probe_models():
    names = []

    def add(api_base):
        name = f"egress-probe-{uuid.uuid4().hex[:8]}"
        body = {
            "model_name": name,
            "litellm_params": {"model": "openai/fake", "api_base": api_base, "api_key": "dummy"},
        }
        response = httpx2.post(f"{LITELLM}/model/new", json=body, headers=_headers(), timeout=20)
        assert response.status_code == 200, response.text
        names.append(response.json()["model_id"])
        return name

    yield add
    for model_id in names:
        httpx2.post(
            f"{LITELLM}/model/delete", json={"id": model_id}, headers=_headers(), timeout=20
        )


def _chat(model):
    return httpx2.post(
        f"{LITELLM}/chat/completions",
        json={"model": model, "messages": [{"role": "user", "content": "ping"}]},
        headers=_headers(),
        timeout=60,
    )


def test_12_e1_litellm_reaches_an_allowlisted_provider_through_the_proxy(probe_models):
    # LiteLLM has no direct route out, so a 200 here proves it honours HTTP(S)_PROXY.
    response = _chat(probe_models(f"{ALLOWED}/v1"))
    assert response.status_code == 200, response.text
    assert response.json()["choices"][0]["message"]["content"]


def test_12_e1_litellm_cannot_reach_a_provider_outside_the_allowlist(probe_models):
    response = _chat(probe_models(f"{DENIED}/v1"))
    assert response.status_code >= 400
