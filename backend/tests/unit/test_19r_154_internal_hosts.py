"""FOLLOWUP-154 (T-18k2-0005 B1): `ingest-raw` runs in the backend container and asks the API for
embeddings over HTTP (`HttpEmbedClient` -> `http://backend:8000/internal/embed`, C10). The
backend's own `ALLOWED_INTERNAL_HOSTS` must name `backend`, or every accepted file fails with
`EgressDenied` (OFFLINE refuses the "external" host). The worker services already add it; the
integration tests injected `LocalEmbedClient`, so the HTTP path never ran.
"""

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import anyio
import pytest
import yaml

from ffcore.core import egress
from ffcore.knowledge import ingest

COMPOSE = Path(__file__).resolve().parents[3] / "deploy" / "docker-compose.yml"


def _backend_hosts_value() -> str:
    services = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))["services"]
    return services["backend"]["environment"]["ALLOWED_INTERNAL_HOSTS"]


def _expand(value: str, env: dict[str, str]) -> list[str]:
    """`${NAME:-default}` as compose expands it, with the given environment."""
    text = re.sub(r"\$\{(\w+):-([^}]*)\}", lambda m: env.get(m[1]) or m[2], value)
    return [part.strip() for part in text.split(",") if part.strip()]


def test_19r_154_backend_allows_itself():
    hosts = _expand(_backend_hosts_value(), {})
    assert "backend" in hosts
    # the operator's extra hosts are still appended, not replaced
    assert _expand(_backend_hosts_value(), {"ALLOWED_INTERNAL_HOSTS": "x.test"}) == [
        "backend",
        "x.test",
    ]


class _Embed(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        length = int(self.headers["Content-Length"])
        texts = json.loads(self.rfile.read(length))["texts"]
        body = json.dumps(
            {
                "model": self.server.model,
                "dense": [[0.0, 1.0] for _ in texts],
                "sparse": [{"1": 0.5} for _ in texts],
                "truncated": [False for _ in texts],
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def embed_server(settings):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Embed)
    server.model = settings.embed_model
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server.server_address[1]
    server.shutdown()


def test_19r_154_http_embed_client_reaches_backend(settings, embed_server, monkeypatch):
    """The real client, with the backend container's settings (OFFLINE, hosts from compose)."""

    async def resolve(host, port):
        assert host == "backend"
        return ["127.0.0.1"]

    monkeypatch.setattr(egress, "system_resolver", resolve)
    backend_settings = settings.model_copy(
        update={
            "offline": True,
            "allowed_internal_hosts": _expand(_backend_hosts_value(), {}),
            "internal_api_url": f"http://backend:{embed_server}",
        }
    )
    result = anyio.run(ingest.HttpEmbedClient(backend_settings).embed, ["a", "b"])
    assert len(result.dense) == 2
