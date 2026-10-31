import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ffcore.api import api_router, internal
from ffcore.api.upload_limit import UploadSizeLimit
from ffcore.core.audit import ensure_audit_partitions
from ffcore.core.auth import register_credential_resolver
from ffcore.core.config import get_settings
from ffcore.core.errors import install_error_handlers
from ffcore.core.logging import AccessLogMiddleware, configure_logging
from ffcore.core.readiness import router as readiness_router
from ffcore.core.readiness import warmup
from ffcore.core.session import session_resolver
from ffcore.core.tracing import init_tracing, shutdown_tracing
from ffcore.knowledge.embed import probe_dimension
from ffcore.services import catalog_events
from ffcore.services.keys import api_key_resolver
from ffcore.services.litellm_reconcile import background_scheduler
from ffcore.services.providers import register_embedding_probe

log = logging.getLogger("ffcore.main")

# Console sessions (03a); resolve_actor stays the single verification point (C2).
register_credential_resolver(session_resolver)
# API keys (03c): `Bearer ffk_...`, after the service token and the session cookie.
register_credential_resolver(api_key_resolver)
# 04a: the in-process embedding model measures its own dimension for 03a's model registration.
register_embedding_probe("local_flagembedding", probe_dimension)


@asynccontextmanager
async def lifespan(app: FastAPI):
    def settings():
        # The request dependency, so an override (tests) applies to the background run too.
        return app.dependency_overrides.get(get_settings, get_settings)()

    # 02: one log configuration, secrets scrubbed, third-party HTTP loggers quiet (FOLLOWUP-49).
    configure_logging(settings())
    # 02: Langfuse client; a half or non-internal configuration stops the start-up here.
    app.state.langfuse = init_tracing(settings())
    # The schema comes from the migrate service; this only adds missing monthly partitions.
    await ensure_audit_partitions(2)

    # 01: LiteLLM's models follow the tables. One reconcile at start and one after each catalog
    # change, in the background; a failure is logged and retried, start-up goes on (S4).

    scheduler = None
    if settings().litellm_url:
        scheduler = background_scheduler(settings)
        catalog_events.subscribe(scheduler.on_change)
        scheduler.on_change()
    else:
        log.error("litellm_not_configured LITELLM_URL is not set; model calls will fail")
    app.state.litellm_scheduler = scheduler
    # 04a: models load in the background; /readyz answers 503 "warming" until they are in.
    warming = asyncio.create_task(warmup(settings()))
    yield
    warming.cancel()
    if scheduler is not None:
        catalog_events.unsubscribe(scheduler.on_change)
        # FOLLOWUP-90: a reconcile cut short must not leave its transaction open.
        await scheduler.stop()
    shutdown_tracing()  # flushes what is still buffered


app = FastAPI(title="FFCore", lifespan=lifespan)
install_error_handlers(app)
# 04a: upload size checked before the multipart body is parsed (review r1 MAJOR-5).
app.add_middleware(UploadSizeLimit)
# 02 r1: the access line, outermost (method, path, status, duration; no query string).
app.add_middleware(AccessLogMiddleware)
app.include_router(api_router)
app.include_router(internal.router)
app.include_router(readiness_router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
