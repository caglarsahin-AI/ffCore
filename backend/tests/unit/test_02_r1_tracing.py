"""02 review r1, tracing life cycle: MAJOR-3 (the process exits by itself within the limit) and
MAJOR-4 (one export has an absolute wall-clock budget). Real SDK, real loopback HTTP server that
answers 200 and then trickles its body, a real child process; no stubs, no network beyond
127.0.0.1. A child the test has to kill is a failure."""

import logging
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SpanExportResult

from ffcore.core import tracing
from ffcore.core.tracing import ReportingExporter

BACKEND = Path(__file__).resolve().parents[2]
TRICKLE_S = 0.1


class _Trickle(BaseHTTPRequestHandler):
    """Reads the OTLP request, answers 200 and sends one byte of a long body every 0.1 s: each
    socket read succeeds, so a per-read timeout never fires."""

    def log_message(self, *args):
        pass

    def do_POST(self):
        self.rfile.read(int(self.headers.get("content-length", 0)))
        self.send_response(200)
        self.send_header("content-type", "application/x-protobuf")
        self.send_header("content-length", "100000")
        self.end_headers()
        try:
            for _ in range(100000):
                self.wfile.write(b"\0")
                self.wfile.flush()
                time.sleep(TRICKLE_S)
        except OSError:
            pass


@pytest.fixture
def trickle():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Trickle)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def _span():
    span = TracerProvider().get_tracer("test-02-r1").start_span("s")
    span.end()
    return span


def test_02_r1_m4_export_budget_is_absolute(trickle, caplog):
    conf = tracing.LangfuseConfig(host=trickle, public_key="pk-lf-x", secret_key="sk-lf-x")
    exporter = ReportingExporter(tracing._otlp_exporter(conf))
    started = time.monotonic()
    with caplog.at_level(logging.ERROR, logger="ffcore"):
        result = exporter.export([_span()])
    elapsed = time.monotonic() - started
    assert result is SpanExportResult.FAILURE
    assert elapsed < tracing.EXPORT_TIMEOUT_S + 1, elapsed
    assert "trace_delivery_failed spans=1 reason=deadline" in caplog.text


def test_02_r1_m4_stuck_export_drops_next_batch(caplog):
    release = threading.Event()

    class _Hang:
        def export(self, spans):
            release.wait()
            return SpanExportResult.SUCCESS

        def shutdown(self):
            pass

        def force_flush(self, timeout_millis=30000):
            return True

    exporter = ReportingExporter(_Hang(), deadline_s=0.2)
    try:
        with caplog.at_level(logging.ERROR, logger="ffcore"):
            assert exporter.export([object()]) is SpanExportResult.FAILURE
            started = time.monotonic()
            assert exporter.export([object(), object()]) is SpanExportResult.FAILURE
            assert time.monotonic() - started < 0.1  # no second thread on a stuck connection
        assert "trace_delivery_failed spans=2 reason=previous_export_stuck" in caplog.text
    finally:
        release.set()


CHILD = """
import sys, time
from pydantic import SecretStr
from ffcore.core import tracing
from ffcore.core.config import Settings
from tests.dummy import SETTINGS_03A

settings = Settings(
    deploy_profile="llmaas", offline=False,
    service_token="dummy-not-secret-service-token-0123456789",
    obo_jwt_secret="dummy-not-secret-obo-jwt-secret-0123456789",
    egress_allowlist=[], allowed_internal_hosts=["127.0.0.0/8"],
    langfuse_host=sys.argv[1], langfuse_public_key=SecretStr("pk-lf-dummy-not-secret"),
    langfuse_secret_key=SecretStr("sk-lf-dummy-not-secret"), **SETTINGS_03A,
)
tracing.init_tracing(settings)
with tracing.span("child-span"):
    pass
started = time.monotonic()
tracing.shutdown_tracing()
print(f"shutdown_returned {time.monotonic() - started:.1f}", flush=True)
"""


def test_02_r1_m3_child_process_exits_by_itself(trickle):
    limit = tracing.SHUTDOWN_TIMEOUT_S + 5
    started = time.monotonic()
    try:
        child = subprocess.run(
            [sys.executable, "-c", CHILD, trickle],
            cwd=BACKEND,
            capture_output=True,
            text=True,
            timeout=limit,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(f"child did not exit within {limit} s (killed by the test)")
    elapsed = time.monotonic() - started
    assert child.returncode == 0, child.stderr[-2000:]
    assert "shutdown_returned" in child.stdout
    assert "trace_delivery_failed" in child.stderr
    assert elapsed < tracing.SHUTDOWN_TIMEOUT_S + 3, elapsed
