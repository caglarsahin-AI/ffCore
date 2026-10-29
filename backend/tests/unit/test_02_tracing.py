"""Package 02: tracing configuration rules, delivery failures, prompts, init script, smoke."""

import importlib.util
import json
import logging
import subprocess
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from opentelemetry import trace as otel
from opentelemetry.sdk.trace.export import SpanExportResult
from pydantic import SecretStr

from ffcore.core import tracing
from ffcore.core.prompts import PromptStore, PromptUnavailable
from ffcore.core.tracing import ReportingExporter, TracingConfigError, langfuse_config

REPO = Path(__file__).resolve().parents[3]
PK, SK = "pk-lf-dummy-not-secret-02", "sk-lf-dummy-not-secret-02"


@pytest.fixture
def lf(settings):
    settings.langfuse_host = "http://langfuse-web:3000"
    settings.langfuse_public_key = SecretStr(PK)
    settings.langfuse_secret_key = SecretStr(SK)
    settings.allowed_internal_hosts = ["langfuse-web"]
    return settings


# --- 8: configuration is explicit; S3 conditions 1, 2, 4, 5 ---


def test_02_8_none_configured_is_disabled(settings, caplog):
    settings.langfuse_host = settings.langfuse_public_key = settings.langfuse_secret_key = None
    with caplog.at_level(logging.WARNING, logger="ffcore"):
        assert langfuse_config(settings) is None
    assert "langfuse_disabled" in caplog.text


@pytest.mark.parametrize("missing", ["langfuse_host", "langfuse_public_key", "langfuse_secret_key"])
def test_02_8_half_config_is_loud(lf, missing):
    setattr(lf, missing, None)
    with pytest.raises(TracingConfigError, match=missing.upper()):
        langfuse_config(lf)


def test_02_8_keys_without_host_never_reach_the_cloud_default(lf):
    # The SDK's own default is Langfuse Cloud; FFCore never lets it fall back to it (S3-1).
    lf.langfuse_host = None
    with pytest.raises(TracingConfigError, match="LANGFUSE_HOST"):
        tracing.init_tracing(lf)


def test_02_8_external_host_refused(lf):
    lf.langfuse_host = "https://cloud.langfuse.com"
    with pytest.raises(TracingConfigError, match="ALLOWED_INTERNAL_HOSTS"):
        langfuse_config(lf)


def test_02_8_global_tracer_provider_untouched(lf):
    before = otel.get_tracer_provider()
    client = tracing.init_tracing(lf)
    try:
        assert client is not None
        assert otel.get_tracer_provider() is before
    finally:
        tracing.shutdown_tracing()


def test_02_8_reinit_after_shutdown_is_fresh(lf):
    # The SDK keeps one resource manager per public key and keeps it after shutdown: a second
    # client with the same key would get the stopped one (old host, old exporter, queues with
    # no consumer, flush waits forever). shutdown_tracing drops it; the new host is used.
    first = tracing.init_tracing(lf)
    old_resources, old_exporter = first._resources, tracing._exporter
    tracing.shutdown_tracing()
    lf.langfuse_host = "http://langfuse-other:3000"
    lf.allowed_internal_hosts = ["langfuse-other"]
    second = tracing.init_tracing(lf)
    try:
        assert second._resources is not old_resources
        assert second._resources.tracer_provider is not old_resources.tracer_provider
        assert tracing._exporter is not old_exporter
    finally:
        tracing.shutdown_tracing()


def test_02_3_shutdown_is_time_bounded(caplog):
    # Process exit never waits on Langfuse: the SDK's flush joins queues without a limit.
    release = threading.Event()
    tracing._client = SimpleNamespace(_resources=object(), shutdown=release.wait)
    started = time.monotonic()
    try:
        with caplog.at_level(logging.ERROR, logger="ffcore"):
            tracing.shutdown_tracing(timeout_s=0.5)
    finally:
        release.set()
    assert time.monotonic() - started < 2
    assert "trace_shutdown_timeout seconds=0.5" in caplog.text
    assert tracing.get_client() is None


def test_02_3_export_timeout_explicit(lf, monkeypatch):
    from opentelemetry.exporter.otlp.proto.http import trace_exporter

    seen = {}
    monkeypatch.setattr(trace_exporter, "OTLPSpanExporter", lambda **kw: seen.update(kw))
    tracing._otlp_exporter(langfuse_config(lf))
    assert seen["timeout"] == tracing.EXPORT_TIMEOUT_S


# --- 3: delivery failures are said, not swallowed ---


class _Failing:
    def __init__(self, outcome):
        self.outcome = outcome

    def export(self, spans):
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis=30000):
        return True


@pytest.mark.parametrize(
    "outcome",
    [ConnectionError(f"refused, Bearer {SK}"), SpanExportResult.FAILURE],
)
def test_02_3_delivery_failure_logged(outcome, caplog):
    exporter = ReportingExporter(_Failing(outcome))
    with caplog.at_level(logging.ERROR, logger="ffcore"):
        assert exporter.export([object(), object()]) is SpanExportResult.FAILURE
    assert "trace_delivery_failed spans=2" in caplog.text
    assert SK not in caplog.text
    assert exporter.failures == 1


def test_02_3_delivery_success_quiet(caplog):
    exporter = ReportingExporter(_Failing(SpanExportResult.SUCCESS))
    with caplog.at_level(logging.DEBUG, logger="ffcore"):
        assert exporter.export([object()]) is SpanExportResult.SUCCESS
    assert "trace_delivery_failed" not in caplog.text


def test_02_2_trace_context_without_trace(lf):
    meta = tracing.trace_context(run_id="r1", user_id="u1", tags=["agent-a"])
    assert meta == {"session_id": "r1", "trace_user_id": "u1", "tags": ["agent-a"]}


# --- 6: prompts ---


class _Prompt(SimpleNamespace):
    def compile(self, **values):
        return self.prompt.replace("{{who}}", values.get("who", ""))


class _Client:
    def __init__(self):
        self.fail = False
        self.calls = 0

    def get_prompt(self, name, label=None, cache_ttl_seconds=None):
        self.calls += 1
        if self.fail:
            raise ConnectionError(f"down, key {SK}")
        assert cache_ttl_seconds == 0  # the SDK cache is off: ours says when it is stale
        return _Prompt(name=name, prompt="Hello {{who}}", version=self.calls)


def test_02_6_prompt_cached(lf):
    now = [0.0]
    client = _Client()
    store = PromptStore(client, ttl_s=60, clock=lambda: now[0])
    assert store.get("greet").compile(who="x") == "Hello x"
    now[0] = 59
    store.get("greet")
    assert client.calls == 1
    now[0] = 61
    store.get("greet")
    assert client.calls == 2


def test_02_6_stale_cache_event(lf, caplog):
    now = [0.0]
    client = _Client()
    store = PromptStore(client, ttl_s=60, clock=lambda: now[0])
    store.get("greet")
    client.fail, now[0] = True, 120
    with caplog.at_level(logging.WARNING, logger="ffcore"):
        assert store.get("greet").version == 1
    assert "prompt_cache_stale name=greet label=production" in caplog.text
    assert SK not in caplog.text


def test_02_6_no_cache_is_loud(lf):
    client = _Client()
    client.fail = True
    with pytest.raises(PromptUnavailable) as err:
        PromptStore(client).get("greet")
    assert err.value.code == "prompt_unavailable" and SK not in err.value.message


def test_02_6_disabled_tracing_is_loud():
    with pytest.raises(PromptUnavailable):
        PromptStore(None).get("greet")


# --- 4: init script prints, never writes ---


def test_02_4_init_script_prints_only(tmp_path):
    result = subprocess.run(
        ["sh", str(REPO / "deploy/langfuse/init.sh")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert list(tmp_path.iterdir()) == []
    lines = dict(
        line.split("=", 1)
        for line in result.stdout.splitlines()
        if line and not line.startswith("#")
    )
    assert lines["LANGFUSE_INIT_PROJECT_PUBLIC_KEY"].startswith("pk-lf-")
    assert lines["LANGFUSE_INIT_PROJECT_SECRET_KEY"].startswith("sk-lf-")
    assert len(lines["LANGFUSE_INIT_USER_PASSWORD"]) >= 24
    again = subprocess.run(
        ["sh", str(REPO / "deploy/langfuse/init.sh")], capture_output=True, text=True
    )
    assert again.stdout != result.stdout  # fresh values every time


# --- 5: smoke fails loud without working keys ---


def _smoke():
    spec = importlib.util.spec_from_file_location("smoke02", REPO / "scripts" / "smoke.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_02_5_smoke_fails_without_keys(monkeypatch):
    smoke = _smoke()
    monkeypatch.setattr(smoke, "_request", lambda url, payload=None, headers=None: (200, b"{}"))
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    with pytest.raises(smoke.SmokeError, match="LANGFUSE_PUBLIC_KEY"):
        smoke.check_langfuse()


def test_02_5_smoke_fails_on_rejected_keys(monkeypatch):
    smoke = _smoke()
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", PK)
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", SK)

    def fake(url, payload=None, headers=None):
        return (401, b"{}") if "projects" in url else (200, b"{}")

    monkeypatch.setattr(smoke, "_request", fake)
    with pytest.raises(smoke.SmokeError, match="401"):
        smoke.check_langfuse()


def test_02_5_smoke_ok(monkeypatch):
    smoke = _smoke()
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", PK)
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", SK)
    monkeypatch.setattr(
        smoke,
        "_request",
        lambda url, payload=None, headers=None: (
            200,
            json.dumps({"data": [{"id": "ffcore"}]}).encode(),
        ),
    )
    assert "projects 200" in smoke.check_langfuse()


def test_02_4_litellm_callback_configured():
    import yaml

    config = yaml.safe_load((REPO / "deploy/litellm/config.yaml").read_text(encoding="utf-8"))
    assert config["litellm_settings"]["callbacks"] == ["langfuse"]
