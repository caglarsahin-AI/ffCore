"""Readiness (`GET /readyz`) and model warmup (04a, moved from 00).

`/healthz` says the process is up; `/readyz` says it can serve: models warmed, configuration
consistent. Every failing check is named with a code; nothing is reported ready by default.
Checks:
  warmup          embedding model and reranker loaded (in worker threads, PayCore warmup.py)
  models          which models serve; FAKE_EMBED=1 is stated, never hidden
  embed_dim       chunks.embedding column size equals EMBED_DIM (P5)
  ollama_context  with INFERENCE_BACKEND=ollama: OLLAMA_CONTEXT_LENGTH is set and not below
                  any active Ollama model's limits.context_tokens (C13); skipped, with the
                  reason, when there is no Ollama model. The runtime num_ctx Ollama applies is
                  not verified here (FOLLOWUP-31, needs the model loaded).
  vector_store    the configured driver answers (Qdrant reachable; pgvector column present)
  llm_slots       (06a) the model slot pool: in use / LLM_SLOTS and waiting per class; skipped
                  without REDIS_URL, failed when Redis does not answer (runs cannot start)
06a extends ollama_context with published agents' limits.context_tokens on Ollama models: an
install or seed change that would cut a published agent's budget is said here (C13).
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
    from ffcore.core import db
    from ffcore.models.catalog import Model, Provider

    async with db.session_scope() as session:
        limits = (
            await session.scalars(
                select(Model.limits)
                .join(Provider, Provider.id == Model.provider_id)
                .where(
                    Provider.driver == "ollama",
                    Model.category == "llm",
                    Model.is_active,
                    Model.deleted_at.is_(None),
                )
            )
        ).all()
    needed = [int(lim["context_tokens"]) for lim in limits if lim.get("context_tokens")]
    needed += await _published_agent_context(db, Model, Provider)
    if not needed:
        return ReadinessCheck(
            name="ollama_context",
            status="skipped",
            code=None,
            detail="no active Ollama model with limits.context_tokens",
        )
    configured = settings.ollama_context_length
    ok = configured is not None and configured >= max(needed)
    return check(
        "ollama_context",
        ok,
        "context_configuration_invalid",
        f"OLLAMA_CONTEXT_LENGTH={configured}, largest context_tokens={max(needed)}",
    )


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
