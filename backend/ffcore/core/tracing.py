"""Langfuse tracing (package 02): one client for the backend process.

Model calls are traced by LiteLLM's own Langfuse callback (cost from models.pricing, 02 S1-S2);
this module traces what the backend does around them and nests LiteLLM's generation under it
through request metadata (`trace_context`). Rules:

- Explicit configuration: LANGFUSE_HOST, _PUBLIC_KEY and _SECRET_KEY all set, or none (tracing
  off, said once). Half of them is an error at start-up, never the SDK's cloud default (S3-1).
- The host must be internal (ALLOWED_INTERNAL_HOSTS): the SDK exports with its own HTTP client,
  outside SafeOutboundClient, so a trace can only go where policy already allows (S3-2).
- The SDK gets a tracer provider of its own; the global OpenTelemetry provider is not touched
  (S3-4).
- A failed export is logged as `trace_delivery_failed` with the span count and the error type;
  the request it belongs to is never held up or failed by it (rule c).
"""

import base64
import logging
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

from ffcore.core.config import Settings
from ffcore.core.egress import EgressPolicy

log = logging.getLogger("ffcore.tracing")

_SETTINGS = ("langfuse_host", "langfuse_public_key", "langfuse_secret_key")
EXPORT_TIMEOUT_S = 5  # one OTLP export, retries included
SHUTDOWN_TIMEOUT_S = 10  # flush at shutdown; then the rest is dropped (trace_shutdown_timeout)
_client: Any = None
_exporter: "ReportingExporter | None" = None


class TracingConfigError(RuntimeError):
    """Langfuse is configured in a way FFCore refuses; the backend does not start."""


@dataclass(frozen=True)
class LangfuseConfig:
    host: str
    public_key: str
    secret_key: str = field(repr=False)


def langfuse_config(settings: Settings) -> LangfuseConfig | None:
    values = {name: getattr(settings, name) for name in _SETTINGS}
    if not any(values.values()):
        log.warning("langfuse_disabled LANGFUSE_HOST/_PUBLIC_KEY/_SECRET_KEY are not set")
        return None
    missing = [name.upper() for name, value in values.items() if not value]
    if missing:
        raise TracingConfigError(f"Langfuse is half configured; not set: {', '.join(missing)}")
    host = settings.langfuse_host.rstrip("/")
    hostname = urlsplit(host).hostname or ""
    if urlsplit(host).scheme not in ("http", "https") or not EgressPolicy(settings).is_internal(
        hostname
    ):
        raise TracingConfigError(
            "LANGFUSE_HOST must be an http(s) URL of a host in ALLOWED_INTERNAL_HOSTS"
        )
    return LangfuseConfig(
        host=host,
        public_key=settings.langfuse_public_key.get_secret_value(),
        secret_key=settings.langfuse_secret_key.get_secret_value(),
    )


class ReportingExporter(SpanExporter):
    """The SDK exports in a background thread; a failure there reaches only the SDK's logger,
    which stays at WARNING (core/logging.py). This says it in ours, without the error text."""

    def __init__(self, inner: SpanExporter) -> None:
        self._inner = inner
        self.failures = 0

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        try:
            result = self._inner.export(spans)
        except Exception as exc:  # noqa: BLE001 - reported, then a normal failure result
            result, reason = SpanExportResult.FAILURE, type(exc).__name__
        else:
            reason = result.name
        if result is not SpanExportResult.SUCCESS:
            self.failures += 1
            log.error("trace_delivery_failed spans=%d reason=%s", len(spans), reason)
        return result

    def shutdown(self) -> None:
        self._inner.shutdown()

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        return self._inner.force_flush(timeout_millis)


def _otlp_exporter(conf: LangfuseConfig) -> SpanExporter:
    """The exporter the SDK would build itself (its OTLP endpoint), built here to be wrapped."""
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    token = base64.b64encode(f"{conf.public_key}:{conf.secret_key}".encode()).decode("ascii")
    return OTLPSpanExporter(
        endpoint=f"{conf.host}/api/public/otel/v1/traces",
        headers={"Authorization": f"Basic {token}", "x-langfuse-public-key": conf.public_key},
        timeout=EXPORT_TIMEOUT_S,
    )


def init_tracing(settings: Settings) -> Any:
    """Creates the process's Langfuse client (None when tracing is off). Called at start-up."""
    global _client, _exporter
    shutdown_tracing()  # a second init replaces the first, never reuses its resources
    conf = langfuse_config(settings)
    if conf is None:
        _client, _exporter = None, None
        return None
    from langfuse import Langfuse

    _exporter = ReportingExporter(_otlp_exporter(conf))
    _client = Langfuse(
        public_key=conf.public_key,
        secret_key=conf.secret_key,
        base_url=conf.host,
        tracer_provider=TracerProvider(),
        span_exporter=_exporter,
    )
    return _client


def get_client() -> Any:
    return _client


def shutdown_tracing(timeout_s: float = SHUTDOWN_TIMEOUT_S) -> None:
    """Flushes and stops the client, waiting at most `timeout_s`: the SDK's flush joins its
    queues without a limit, and process exit never waits on Langfuse (what is not sent by then
    is lost and said). The SDK keeps its resource manager per public key after shutdown and
    hands the stopped one to the next client with that key (old host and exporter, queues nobody
    drains; langfuse 4.15.1). It is dropped here, so the next init_tracing starts fresh."""
    global _client, _exporter
    if _client is not None:
        from langfuse._client.resource_manager import LangfuseResourceManager

        resources = _client._resources
        worker = threading.Thread(target=_client.shutdown, name="langfuse-shutdown", daemon=True)
        worker.start()
        worker.join(timeout_s)
        if worker.is_alive():
            log.error("trace_shutdown_timeout seconds=%s", timeout_s)
        with LangfuseResourceManager._lock:
            for key, instance in list(LangfuseResourceManager._instances.items()):
                if instance is resources:
                    del LangfuseResourceManager._instances[key]
    _client, _exporter = None, None


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[Any]:
    """An observation around backend work; nothing when tracing is off."""
    if _client is None:
        yield None
        return
    with _client.start_as_current_observation(name=name, as_type="span", **attributes) as obs:
        yield obs


@contextmanager
def run_attributes(
    run_id: str, user_id: str | None, project_id: str | None, tags: Sequence[str] = ()
) -> Iterator[None]:
    """Session = run, user, project and tags for every observation inside (brief 02 madde 3)."""
    from langfuse import propagate_attributes

    metadata = {"project_id": project_id} if project_id else None
    with propagate_attributes(
        user_id=user_id, session_id=run_id, metadata=metadata, tags=list(tags) or None
    ):
        yield


def trace_context(
    run_id: str | None = None, user_id: str | None = None, tags: Sequence[str] = ()
) -> dict[str, Any]:
    """LiteLLM request metadata that puts LiteLLM's generation under the current observation
    (measured on v1.80.0 + Langfuse 3.120.0, 02 slice 1) and carries session, user and tags."""
    meta: dict[str, Any] = {}
    if _client is not None:
        trace_id = _client.get_current_trace_id()
        observation_id = _client.get_current_observation_id()
        if trace_id:
            meta["existing_trace_id"] = trace_id
        if observation_id:
            meta["parent_observation_id"] = observation_id
    if run_id:
        meta["session_id"] = run_id
    if user_id:
        meta["trace_user_id"] = user_id
    if tags:
        meta["tags"] = list(tags)
    return meta


def langgraph_handler() -> Any:
    """Langfuse callback handler for LangGraph runs (06a). langchain arrives with 06a; until then
    asking for the handler is an explicit error, not a silent no-op."""
    if _client is None:
        raise TracingConfigError("Langfuse tracing is off; no LangGraph handler")
    try:
        from langfuse.langchain import CallbackHandler
    except ImportError as exc:
        raise TracingConfigError(f"LangGraph handler needs langchain ({exc.name})") from None
    return CallbackHandler()
