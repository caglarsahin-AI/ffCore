"""Package 02 (FOLLOWUP-49): one log configuration; secrets never reach the log output.

The output of the configured handler is captured (not caplog, which bypasses the handler and its
filter). DEBUG is on, so third-party loggers would speak if they were not held at WARNING.
"""

import io
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import anyio
import pytest
from pydantic import SecretStr

from ffcore.core.egress import EgressTimeout, SafeOutboundClient
from ffcore.core.logging import QUIET_LOGGERS, configure_logging, scrub

SECRET = "dummy-not-secret-02-SENTINEL"
HEADER_VALUE = "dummy-not-secret-02-HEADER"


@pytest.fixture
def output(settings):
    settings.service_token = SecretStr(SECRET + "-service-token-0123456789")
    settings.litellm_master_key = SecretStr("sk-" + SECRET)
    stream = io.StringIO()
    configure_logging(settings, level="DEBUG", stream=stream)
    yield stream
    configure_logging(settings, level="WARNING", stream=io.StringIO())


class _Header(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(200)
        self.send_header("x-provider-token", HEADER_VALUE)
        self.send_header("content-length", "2")
        self.end_headers()
        self.wfile.write(b"ok")


def test_02_9_scrub_filter_secrets(settings, output):
    log = logging.getLogger("ffcore.test02")
    log.debug("calling with %s", settings.service_token.get_secret_value())
    log.info("Authorization: Bearer %s", "abcdef0123456789")
    log.warning("config api_key='%s' password=%s", "xyz-123456", "hunter2-xyz")
    log.error("url postgresql://ffcore:%s@postgres:5432/ffcore", "pw-0123456")
    text = output.getvalue()
    assert SECRET not in text
    assert "abcdef0123456789" not in text and "xyz-123456" not in text
    assert "hunter2-xyz" not in text and "pw-0123456" not in text
    assert text.count("***") >= 5


def test_02_9_exception_text_scrubbed(settings, output):
    log = logging.getLogger("ffcore.test02")
    try:
        raise RuntimeError(f"failed with sk-{SECRET} and Bearer {SECRET}")
    except RuntimeError:
        log.exception("boom")
    text = output.getvalue()
    assert "boom" in text and "RuntimeError" in text
    assert SECRET not in text


def test_02_9_third_party_http_loggers_quiet(settings, output):
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Header)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    settings.allowed_internal_hosts = ["127.0.0.0/8"]

    async def call():
        async with SafeOutboundClient(
            timeout=EgressTimeout(connect=2, read=2, total=5), settings=settings
        ) as client:
            return await client.request("GET", f"http://127.0.0.1:{server.server_address[1]}/")

    try:
        assert anyio.run(call).status_code == 200
    finally:
        server.shutdown()
    text = output.getvalue()
    assert HEADER_VALUE not in text
    assert "receive_response_headers" not in text
    for name in QUIET_LOGGERS:
        assert logging.getLogger(name).getEffectiveLevel() >= logging.WARNING


def test_02_9_uvicorn_handlers_filtered(settings, output):
    access = logging.getLogger("uvicorn.access")
    handler = logging.StreamHandler(io.StringIO())
    access.addHandler(handler)
    try:
        configure_logging(settings, level="DEBUG", stream=output)
        access.info('"GET /x?api_key=%s HTTP/1.1" 200', "dummy-not-secret-02-query")
        assert "dummy-not-secret-02-query" not in handler.stream.getvalue()
    finally:
        access.removeHandler(handler)


@pytest.mark.parametrize(
    ("text", "leak"),
    [
        ("Bearer abc.def-ghi_123", "abc.def-ghi_123"),
        ("token=AbC123xyz", "AbC123xyz"),
        ('"secret": "s3cr3t-value"', "s3cr3t-value"),
        ("pk-lf-0123456789abcdef", "pk-lf-0123456789abcdef"),
        ("redis://:pw-redis-123@redis:6379/0", "pw-redis-123"),
    ],
)
def test_02_9_scrub_patterns(text, leak):
    assert leak not in scrub(text, ())
