"""Readiness (`GET /readyz`) and model warmup (04a, moved from 00).

`/healthz` says the process is up; `/readyz` says it can serve: models warmed, configuration
consistent. Every failing check is named with a code; nothing is reported ready by default.
Checks:
  warmup          embedding model and reranker loaded (in worker threads, PayCore warmup.py)
  models          which models serve; FAKE_EMBED=1 is stated, never hidden
  embed_dim       chunks.embedding column size equals EMBED_DIM (P5)
  ollama_context  with INFERENCE_BACKEND=ollama: OLLAMA_CONTEXT_LENGTH is set and not below
                  the largest needed context (C13): every active Ollama model's
                  limits.context_window (the key ModelLimits, the seed and the console write;
                  FOLLOWUP-219) and every published agent's limits.context_tokens on an Ollama
                  model (06a). Skipped, with the reason, when neither exists.
  ollama_runtime_context
                  (04b-2, FOLLOWUP-31) what Ollama really runs with: `/api/ps`
                  `models[].context_length` of each loaded model against the same largest
                  needed context; smaller → context_configuration_invalid, the field missing →
                  ollama_ps_unexpected (never a silent pass), no model loaded → skipped with the
                  model names. Written to Ollama's API documentation; not yet verified against the
                  pinned ollama 0.12.6 image (ENV-204).
  vector_store    the configured driver answers (Qdrant reachable; pgvector column present)
  llm_slots       (06a) the model slot pool: in use / LLM_SLOTS and waiting per class; skipped
                  without REDIS_URL, failed when Redis does not answer (runs cannot start)
  ingest_queue    (04b-2, FOLLOWUP-86) jobs waiting in the ingest queue (arq, Redis); information
                  only, no threshold; skipped without REDIS_URL, failed when Redis does not answer
A model's own window is checked without any agent (FOLLOWUP-219); 06a's published agents add
their budgets, so an install or seed change that would cut one is said here (C13).
"""

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import select

from ffcore.api.knowledge_schemas import ReadinessCheck, ReadyzOut
from ffcore.core.config import Settings, get_settings

log = logging.getLogger("ffcore.readiness")
router = APIRouter(tags=["readiness"])

_state: dict = {"warm": False, "error": None, "code": None}


def reset() -> None:
    _state.update(warm=False, error=None, code=None)


def _load_models(settings: Settings) -> None:
    from ffcore.knowledge.embed import get_embedder
    from ffcore.knowledge.rerank import get_reranker

    for model in (get_embedder(settings), get_reranker(settings)):
        load = getattr(model, "load", None)
        if load is not None:
            load()
    from ffcore.guardrails.recognizers.ner import local_ner
    from ffcore.guardrails.settings import get_guardrail_settings

    guard = get_guardrail_settings()
    if guard.guardrail_egress_enabled and guard.guardrail_egress_ner:
        # 08 tam 1b: egress needs the NER model; a missing weight is `model_missing` here.
        local_ner().load()


async def warmup(settings: Settings) -> None:
    """Load the models once, off the event loop; a failure is kept and reported by /readyz."""
    try:
        await asyncio.to_thread(_load_models, settings)
    except Exception as exc:  # noqa: BLE001 - reported as warmup_failed, never swallowed
        log.error("warmup failed: %s", type(exc).__name__)
        # ModelMissing (r1 MAJOR-6) names the model and the path it was looked for in.
        code = getattr(exc, "code", None) or "warmup_failed"
        _state.update(warm=False, error=f"{type(exc).__name__}: {str(exc)[:300]}", code=code)
        return
    _state.update(warm=True, error=None)


def check(name: str, ok: bool, code: str | None = None, detail: str | None = None):
    return ReadinessCheck(
        name=name, status="ok" if ok else "failed", code=None if ok else code, detail=detail
    )


async def _embed_dim_check(settings: Settings) -> ReadinessCheck:
    from ffcore.knowledge.vectorstore.pgvector import PgVectorStore

    actual = await PgVectorStore().column_dim()
    return check(
        "embed_dim",
        actual == settings.embed_dim,
        "embed_dim_mismatch",
        f"chunks.embedding vector({actual}), EMBED_DIM {settings.embed_dim}",
    )


async def _ollama_context_check(settings: Settings) -> ReadinessCheck:
    if settings.inference_backend != "ollama":
        return ReadinessCheck(
            name="ollama_context",
            status="skipped",
            code=None,
            detail=f"INFERENCE_BACKEND={settings.inference_backend}",
        )
    _, needed = await _context_needs(settings)
    if not needed:
        return ReadinessCheck(
            name="ollama_context",
            status="skipped",
            code=None,
            detail=NO_NEED,
        )
    configured = settings.ollama_context_length
    ok = configured is not None and configured >= max(needed)
    return check(
        "ollama_context",
        ok,
        "context_configuration_invalid",
        f"OLLAMA_CONTEXT_LENGTH={configured}, largest needed context={max(needed)}",
    )


NO_NEED = "no active Ollama model with limits.context_window and no published agent on Ollama"


async def _context_needs(settings: Settings):
    """Active Ollama LLM models (provider id, encrypted config, model_id) and the context sizes
    Ollama must hold: each model's limits.context_window (FOLLOWUP-219: ModelLimits has no
    context_tokens, so an old key in a row is not counted) and published agents' budgets (06a)."""
    from ffcore.core import db
    from ffcore.models.catalog import Model, Provider

    async with db.session_scope() as session:
        rows = (
            await session.execute(
                select(Provider.id, Provider.config_encrypted, Model.model_id, Model.limits)
                .join(Provider, Provider.id == Model.provider_id)
                .where(
                    Provider.driver == "ollama",
                    Model.category == "llm",
                    Model.is_active,
                    Model.deleted_at.is_(None),
                )
            )
        ).all()
    needed = [int(r.limits["context_window"]) for r in rows if r.limits.get("context_window")]
    needed += await _published_agent_context(db, Model, Provider)
    return rows, needed


class OllamaPsUnexpected(Exception):
    """Ollama answered `/api/ps`, but not in the documented shape (r2 NOTE-1)."""


def _ollama_name(name: str) -> str:
    """Ollama lists an untagged model as `<name>:latest` (r2 MINOR-2)."""
    return name if ":" in name else f"{name}:latest"


async def _ollama_ps(config_encrypted: bytes, settings: Settings) -> list[dict]:
    """GET {base_url}/api/ps of one Ollama provider: the models it has loaded."""
    from ffcore.core.egress import EgressTimeout, SafeOutboundClient
    from ffcore.core.secrets import decrypt_json

    base = decrypt_json(config_encrypted, settings)["base_url"].rstrip("/")
    timeout = EgressTimeout(connect=3, read=5, total=8)
    async with SafeOutboundClient(timeout=timeout, settings=settings) as client:
        response = await client.request("GET", f"{base}/api/ps")
    if response.status_code != 200:
        raise RuntimeError(f"/api/ps answered {response.status_code}")
    body = response.json()
    models = body.get("models") if isinstance(body, dict) else None
    if not isinstance(models, list):
        raise OllamaPsUnexpected("/api/ps answer has no models list")
    return models


async def _ollama_runtime_check(settings: Settings) -> ReadinessCheck:
    name = "ollama_runtime_context"
    if settings.inference_backend != "ollama":
        return ReadinessCheck(
            name=name,
            status="skipped",
            code=None,
            detail=f"INFERENCE_BACKEND={settings.inference_backend}",
        )
    rows, needed = await _context_needs(settings)
    if not needed:
        return ReadinessCheck(
            name=name,
            status="skipped",
            code=None,
            detail=NO_NEED,
        )
    largest = max(needed)
    loaded, not_loaded = [], []
    by_provider: dict = {}
    for row in rows:
        by_provider.setdefault(row.id, (row.config_encrypted, set()))[1].add(row.model_id)
    for config_encrypted, model_ids in by_provider.values():
        try:
            running = await _ollama_ps(config_encrypted, settings)
        except OllamaPsUnexpected as exc:
            return check(name, False, "ollama_ps_unexpected", str(exc))
        except Exception as exc:  # noqa: BLE001 - reported with its type, never hidden
            return check(name, False, "ollama_unreachable", type(exc).__name__)
        by_name = {_ollama_name(m.get("name") or m.get("model") or ""): m for m in running}
        for model_id in sorted(model_ids):
            entry = by_name.get(_ollama_name(model_id))
            if entry is None:
                not_loaded.append(model_id)
                continue
            context_length = entry.get("context_length")
            if not isinstance(context_length, int):
                return check(
                    name,
                    False,
                    "ollama_ps_unexpected",
                    f"/api/ps has no context_length for {model_id}",
                )
            loaded.append((model_id, context_length))
    if not loaded:
        return ReadinessCheck(
            name=name,
            status="skipped",
            code=None,
            detail=f"not loaded: {', '.join(not_loaded)}; checked once a request loads them",
        )
    small = [(m, c) for m, c in loaded if c < largest]
    detail = ", ".join(f"{m}={c}" for m, c in loaded) + f"; largest needed context={largest}"
    if not_loaded:
        detail += f"; not loaded: {', '.join(not_loaded)}"
    return check(name, not small, "context_configuration_invalid", detail)


async def _ingest_queue_check(settings: Settings) -> ReadinessCheck:
    if settings.redis_url is None:
        return ReadinessCheck(
            name="ingest_queue", status="skipped", code=None, detail="REDIS_URL is not set"
        )
    import redis.asyncio as aioredis

    client = aioredis.from_url(settings.redis_url.get_secret_value())
    try:
        queued = await client.zcard(settings.arq_queue_ingest)
    except Exception as exc:  # noqa: BLE001 - reported with its type, never hidden
        return check("ingest_queue", False, "redis_unavailable", type(exc).__name__)
    finally:
        await client.aclose()
    return check("ingest_queue", True, detail=f"queued={queued}")


async def _published_agent_context(db, model, provider) -> list[int]:
    """context_tokens of every published agent version whose model runs on Ollama (06a)."""
    from ffcore.models.agents import Agent, AgentVersion

    async with db.session_scope() as session:
        rows = await session.execute(
            select(AgentVersion.definition)
            .join(Agent, Agent.current_version_id == AgentVersion.id)
            .join(
                model,
                (model.project_id == Agent.project_id)
                & (model.key == AgentVersion.definition["model"].astext),
            )
            .join(provider, provider.id == model.provider_id)
            .where(
                Agent.deleted_at.is_(None),
                Agent.status == "published",
                provider.driver == "ollama",
                model.deleted_at.is_(None),
            )
        )
        return [int(d.get("limits", {}).get("context_tokens", 16000)) for (d,) in rows.all()]


async def _llm_slots_check(settings: Settings) -> ReadinessCheck:
    if settings.redis_url is None:
        return ReadinessCheck(
            name="llm_slots", status="skipped", code=None, detail="REDIS_URL is not set"
        )
    import redis.asyncio as aioredis

    from ffcore.runtime.scheduler import BackgroundWindow, LlmSlots, SlotSettings

    client = aioredis.from_url(settings.redis_url.get_secret_value())
    try:
        window = BackgroundWindow.parse(
            settings.background_window,
            weekends_all_day=settings.background_window_weekends,
            zone=settings.background_window_tz,
        )
        state = await LlmSlots(client, SlotSettings(slots=settings.llm_slots), window).status()
    except Exception as exc:  # noqa: BLE001 - reported with its type, never hidden
        return check("llm_slots", False, "redis_unavailable", type(exc).__name__)
    finally:
        await client.aclose()
    waiting = ", ".join(f"{k}={v}" for k, v in state["waiting"].items())
    window_state = "open" if state["background_window_open"] else "closed"
    return check(
        "llm_slots",
        True,
        detail=f"in_use={state['in_use']}/{state['slots']} waiting: {waiting}; "
        f"background window {window_state}",
    )


async def _vector_store_check(settings: Settings) -> ReadinessCheck:
    from ffcore.knowledge.jobs import get_vector_store
    from ffcore.knowledge.vectorstore.base import VectorStoreError

    try:
        store = get_vector_store(settings)
        if store.name == "qdrant":
            await store._call("GET", "/collections")
    except VectorStoreError as exc:
        return check("vector_store", False, exc.code, settings.vector_backend)
    return check("vector_store", True, detail=settings.vector_backend)


@router.get(
    "/readyz",
    response_model=ReadyzOut,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadyzOut}},
)
async def readyz(settings: Annotated[Settings, Depends(get_settings)]):
    """200 when every check is ok or skipped; 503 with the same body otherwise
    (codes: warming, warmup_failed, model_missing, context_configuration_invalid,
    embed_dim_mismatch, ...)."""
    if _state["warm"]:
        warm = check("warmup", True)
    elif _state["error"]:
        warm = check("warmup", False, _state["code"] or "warmup_failed", _state["error"])
    else:
        warm = check("warmup", False, "warming", "models are loading")
    models = ReadinessCheck(
        name="models",
        status="ok",
        code=None,
        detail=(
            "FAKE_EMBED=1: deterministic test models"
            if settings.fake_embed
            else f"{settings.embed_model}, {settings.rerank_model}"
        ),
    )
    checks = [
        warm,
        models,
        await _embed_dim_check(settings),
        await _ollama_context_check(settings),
        await _vector_store_check(settings),
        await _llm_slots_check(settings),
        await _ollama_runtime_check(settings),
        await _ingest_queue_check(settings),
    ]
    failed = [c for c in checks if c.status == "failed"]
    if not failed:
        state = "ready"
    elif all(c.code == "warming" for c in failed):
        state = "warming"
    else:
        state = "not_ready"
    body = ReadyzOut(status=state, checks=checks)
    code = status.HTTP_200_OK if state == "ready" else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(body.model_dump(mode="json"), status_code=code)
