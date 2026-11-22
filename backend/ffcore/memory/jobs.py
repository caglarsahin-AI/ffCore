"""The extraction job (brief 14 "Yazma" 1-2; C10; K-14-0003 S1).

`enqueue_after_done` is called by the runner after a completed run's `done` event and commit;
the answer never waits for it. The job runs on the `llm-background` queue (the background
worker), but its model call takes the slot as **interactive-low**: it is not held back by
`BACKGROUND_WINDOW`, it only yields to interactive calls (brief 14 "Teknik notlar", C10).

The job: the finished turn (question + answer) and its 5 related items (API), the
`memory_extract` prompt, the turn through 08 `egress` when the stage is on (llmaas: the text
leaves for the provider), the `memory-extract` model (or the settings' model), the schema check,
then the candidates go to the API, which applies the threshold, the PII check, dedupe and the
item limit. The outcome is a `progress` run event `{"memory_extraction": {...}}` with ids and
counts only; a failure is a coded outcome there and in the log, never silent.
"""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from ffcore.core.config import Settings, get_settings
from ffcore.core.errors import ApiError

log = logging.getLogger("ffcore.memory")

JOB_NAME = "extract_memories"


class ExtractionQueue:
    """arq enqueue of `extract_memories` on the background queue; one pool per process."""

    def __init__(self, settings: Settings) -> None:
        if settings.redis_url is None:
            raise RuntimeError("REDIS_URL is not set; the memory job needs Redis")
        self._dsn = settings.redis_url.get_secret_value()
        self._queue_name = settings.arq_queue_background
        self._pool = None

    async def enqueue(self, run_id: str) -> str:
        from arq import create_pool
        from arq.connections import RedisSettings

        if self._pool is None:
            self._pool = await create_pool(RedisSettings.from_dsn(self._dsn))
        job = await self._pool.enqueue_job(JOB_NAME, run_id, _queue_name=self._queue_name)
        if job is None:
            raise RuntimeError(f"memory extraction for run {run_id} was not enqueued")
        return job.job_id


_queue: ExtractionQueue | None = None


def get_queue(settings: Settings):
    global _queue
    if _queue is None:
        _queue = ExtractionQueue(settings)
    return _queue


async def enqueue_after_done(settings: Settings, run_id) -> None:
    """The run is completed and told so; a failure to enqueue is logged with the run id (the run
    stays completed, the answer was given)."""
    try:
        await get_queue(settings).enqueue(str(run_id))
    except Exception as exc:  # noqa: BLE001 - logged loudly, the completed run is not undone
        log.error("memory_extract_enqueue_failed run_id=%s error=%s", run_id, type(exc).__name__)


async def _extract(session: AsyncSession, settings: Settings, ctx: dict, run) -> dict:
    from ffcore.guardrails.service import resolve_policy
    from ffcore.guardrails.settings import get_guardrail_settings
    from ffcore.memory import extract
    from ffcore.memory.recall import HttpMemory
    from ffcore.models.agents import AgentVersion
    from ffcore.runtime.adapters import EngineGuard, LiteLLMModel
    from ffcore.runtime.contracts import JobClass
    from ffcore.runtime.definition import parse_definition
    from ffcore.services.quota import QuotaGate, Subject, engine_for

    memory = ctx.get("memory_client_factory", HttpMemory)(
        settings, run_id=run.id, project_id=run.project_id, user_id=run.user_id
    )
    turn = extract.turn_text(run.input or "", run.output or "")
    related = await memory.related(turn)
    if related.off_reason is not None:
        return {"skipped": related.off_reason}
    version = await session.get(AgentVersion, run.agent_version_id)
    definition = parse_definition(version.definition)
    prompt = ctx["prompts"].get(extract.PROMPT_NAME)
    messages = extract.messages(prompt, turn=turn, known=extract.known_text(related.items))
    guardrail = get_guardrail_settings()
    events = ctx["events"]
    if guardrail.guardrail_egress_enabled:
        policy = await resolve_policy(session, run.project_id, definition.guardrail_policy_key)
        guard = EngineGuard(
            session,
            ctx["redis"],
            events,
            policy,
            run_id=run.id,
            project_id=run.project_id,
            egress_enabled=True,
            token_ttl_s=guardrail.pii_token_ttl_s,
            channel=run.channel,
        )
        checked = await guard.check("egress", messages[0]["content"])
        if checked.action == "block":
            return {"error": "guardrail_block", "reference_id": checked.reference_id}
        messages = [{**messages[0], "content": checked.text}]
    model = ctx.get("memory_model_factory") or LiteLLMModel
    caller = model(
        settings,
        session,
        ctx["slots"],
        run_id=run.id,
        project_id=run.project_id,
        user_id=run.user_id,
        model_key=related.extraction_model or "memory-extract",
        job_class=JobClass.interactive_low,
        quota=QuotaGate(
            engine_for(settings, ctx["redis"]),
            ctx["redis"],
            session,
            Subject(project_id=str(run.project_id), user_id=str(run.user_id), api_key_id=None),
            settings=settings,
        ),
    )
    answer = await caller.call(messages, tools=[], max_tokens=extract.OUTPUT_TOKENS, on_token=None)
    try:
        candidates = extract.parse(answer.content)
    except extract.ExtractInvalid:
        return {"error": extract.ExtractInvalid.code}
    if not candidates:
        return {"candidates": 0, "written": [], "archived": [], "rejected": {}}
    written = await memory.write(
        [
            {
                "kind": c.kind,
                "text": c.text,
                "confidence": c.confidence,
                "supersedes_id": c.supersedes_id,
            }
            for c in candidates
        ]
    )
    return {"candidates": len(candidates), **written}


async def extract_memories(ctx: dict, run_id: str) -> str:
    """arq job on the background worker. Returns the outcome's short name."""
    from ffcore.core import db
    from ffcore.memory.recall import MemoryConflict
    from ffcore.models.runs import Run
    from ffcore.runtime.contracts import RunEventType, RunStatus
    from ffcore.runtime.events import RunEventWriter
    from ffcore.runtime.state import StopRun

    # A test passes its own settings; the worker reads the environment.
    settings = ctx.get("settings") or get_settings()
    async with db.session_scope() as session:
        run = await session.get(Run, uuid.UUID(run_id))
        if run is None or run.status != RunStatus.completed or run.user_id is None:
            log.warning("memory_extract_skipped run_id=%s reason=run_not_eligible", run_id)
            return "skipped"
        events = RunEventWriter(
            session, ctx["redis"], run.id, ttl_s=settings.run_event_stream_ttl_s
        )
        await events.start()
        try:
            outcome = await _extract(session, settings, {**ctx, "events": events}, run)
        except MemoryConflict as conflict:
            outcome = {"skipped": conflict.code}
        except StopRun as stop:
            outcome = {"error": stop.code}
        except ApiError as exc:
            await session.rollback()
            outcome = {"error": exc.code, "detail": getattr(exc, "detail", None)}
        if "error" in outcome:
            log.error("memory_extract_failed run_id=%s code=%s", run_id, outcome["error"])
        await events.record(RunEventType.progress, {"memory_extraction": outcome})
        await session.commit()
    if "error" in outcome:
        return "failed"
    return "skipped" if "skipped" in outcome else "done"
