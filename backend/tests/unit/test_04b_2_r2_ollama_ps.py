"""04b-2 r2 NOTE-1 (P4): `/api/ps` answering 200 without a `models` list is an unexpected answer
(`OllamaPsUnexpected`), not an unreachable Ollama; HTTP errors stay errors of the connection."""

import asyncio
from types import SimpleNamespace

import pytest

from ffcore.core import egress, readiness, secrets


class _Client:
    def __init__(self, status, body):
        self.status, self.body = status, body

    def __call__(self, *, timeout, settings):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def request(self, method, url):
        self.url = url
        return SimpleNamespace(status_code=self.status, json=lambda: self.body)


@pytest.mark.parametrize("body", [{}, {"models": None}, {"models": {"a": 1}}, ["x"]])
def test_04b_2_r2_ps_shape_errors(monkeypatch, body):
    monkeypatch.setattr(secrets, "decrypt_json", lambda token, s: {"base_url": "http://ol:11434"})
    monkeypatch.setattr(egress, "SafeOutboundClient", _Client(200, body))
    with pytest.raises(readiness.OllamaPsUnexpected):
        asyncio.run(readiness._ollama_ps(b"x", None))


def test_04b_2_r2_ps_http_error_is_not_unexpected(monkeypatch):
    monkeypatch.setattr(secrets, "decrypt_json", lambda token, s: {"base_url": "http://ol:11434/"})
    monkeypatch.setattr(egress, "SafeOutboundClient", _Client(500, {}))
    with pytest.raises(Exception) as caught:
        asyncio.run(readiness._ollama_ps(b"x", None))
    assert not isinstance(caught.value, readiness.OllamaPsUnexpected)


def test_04b_2_r2_ps_list_is_returned(monkeypatch):
    client = _Client(200, {"models": [{"name": "m:1", "context_length": 4096}]})
    monkeypatch.setattr(secrets, "decrypt_json", lambda token, s: {"base_url": "http://ol:11434/"})
    monkeypatch.setattr(egress, "SafeOutboundClient", client)
    assert asyncio.run(readiness._ollama_ps(b"x", None)) == [
        {"name": "m:1", "context_length": 4096}
    ]
    assert client.url == "http://ol:11434/api/ps"
