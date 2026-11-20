"""12-1: TLS reverse proxy (FOLLOWUP-66, C16).

Internal listener (8443): console and API over HTTPS. Public listener (9443): only
`/channels/teams/messages` reaches the backend; every other path is the proxy's own 404.
Same stack as test_12_egress.py (its docstring); the test certificate is self-signed and made
for the run outside the repository (TLS_CERT_DIR). Skipped as NOT_RUN without RUN_TLS_TESTS=1.
"""

import os
import socket
import ssl

import httpx2
import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_TLS_TESTS") != "1",
    reason="NOT_RUN: needs RUN_TLS_TESTS=1 and the TLS test stack (test_12_egress.py docstring)",
)

INTERNAL = "https://tls-proxy:8443"
PUBLIC = "https://tls-proxy:9443"
EDGE_HEADER = "x-ffcore-edge"


def get(url, **kwargs):
    with httpx2.Client(verify=False, timeout=15, trust_env=False) as client:
        return client.request(kwargs.pop("method", "GET"), url, **kwargs)


def test_12_tls_internal_listener_serves_the_console():
    response = get(f"{INTERNAL}/")
    assert response.status_code in (200, 307, 308)
    assert EDGE_HEADER not in response.headers
    assert response.headers["strict-transport-security"].startswith("max-age=")


def test_12_tls_internal_listener_reaches_the_backend_api():
    response = get(f"{INTERNAL}/v1/models")
    assert response.status_code == 401  # backend's own answer: no key
    assert "error" in response.json()


def test_12_tls_plain_http_is_not_served_on_the_tls_port():
    response = httpx2.get("http://tls-proxy:8443/", timeout=10, trust_env=False)
    assert response.status_code == 400


@pytest.mark.parametrize("path", ["/", "/v1/models", "/api/v1/auth/me", "/healthz", "/mcp/x/"])
def test_12_tls_public_listener_refuses_every_other_path(path):
    response = get(f"{PUBLIC}{path}")
    assert response.status_code == 404
    assert response.headers[EDGE_HEADER] == "public-denied"


def test_12_tls_public_listener_forwards_the_teams_path_to_the_backend():
    # Package 15 is not merged: the backend itself answers (404 or 405), not the proxy.
    response = get(f"{PUBLIC}/channels/teams/messages", method="POST", json={})
    assert EDGE_HEADER not in response.headers
    assert response.status_code in (401, 403, 404, 405)


def raw_request(port, target):
    """One request with the target exactly as given (no client-side path normalisation)."""
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    with socket.create_connection(("tls-proxy", port), timeout=10) as sock:
        with context.wrap_socket(sock, server_hostname="tls-proxy") as tls:
            tls.sendall(
                f"POST {target} HTTP/1.1\r\nHost: tls-proxy\r\nContent-Length: 2\r\n"
                "Connection: close\r\n\r\n{}".encode()
            )
            data = b""
            while chunk := tls.recv(65536):
                data += chunk
    head = data.split(b"\r\n\r\n", 1)[0].decode("latin-1").lower()
    return int(head.split()[1]), head


@pytest.mark.parametrize(
    "target",
    [
        "/api/v1/auth/me/../../../../channels/teams/messages",
        "/api/v1/auth/me/..%2F..%2F..%2F..%2Fchannels/teams/messages",
        "/foo/../channels/teams/messages",
    ],
)
def test_12_r2_public_listener_sends_only_the_fixed_teams_path(target):
    # r1 MINOR-1: these normalise to the Teams path; the backend answers (no edge header), and
    # with the fixed proxy_pass URI it is sent /channels/teams/messages, never the raw target
    # (the config side is test_12_nginx_public_listener_opens_only_the_teams_path).
    status, head = raw_request(9443, target)
    assert "x-ffcore-edge" not in head
    assert status in (401, 403, 404, 405)


def test_12_r2_public_listener_refuses_a_path_that_normalises_elsewhere():
    status, head = raw_request(9443, "/channels/teams/messages/../../healthz")
    assert status == 404 and "x-ffcore-edge: public-denied" in head
