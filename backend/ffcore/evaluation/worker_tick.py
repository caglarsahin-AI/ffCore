"""The exam advancer tick on the background worker (09, K-09-0007 S4).

Production bindings for runner.advance_eval: the judge (LiteLLM, background class, egress),
the SQL re-read (mcp-sql as the exam's starter), the embedding (API /internal/embed).
"""

import logging

from sqlalchemy import select

from ffcore.core import db
from ffcore.core.audit import AuditEntry, write_event
from ffcore.core.config import Settings
from ffcore.evaluation import judge as judge_mod
from ffcore.evaluation.langfuse_api import LangfuseApi
from ffcore.evaluation.runner import active_runs, advance_eval, parse_csv_rows
from ffcore.evaluation.scorers import Score
from ffcore.guardrails.service import resolve_policy
from ffcore.guardrails.settings import get_guardrail_settings
from ffcore.models.agents import AgentVersion
from ffcore.models.tools import Tool, ToolAction
from ffcore.runtime.contracts import JobClass
from ffcore.runtime.definition import parse_definition

log = logging.getLogger("ffcore.evaluation")


async def tick(settings: Settings, redis, slots, prompts) -> None:
    async with db.session_scope() as session:
        ids = [ev.id for ev in await active_runs(session)]
    if not ids:
        return
    api = LangfuseApi(settings)
    for ev_id in ids:
        async with db.session_scope() as session:
            from ffcore.models.eval import EvalRun

            ev = await session.get(EvalRun, ev_id)
            if ev is None or ev.status != "running":
                continue
            try:
                await advance_eval(
                    session,
                    settings,
                    ev,
                    api=api,
                    redis=redis,
                    judge=_judge(settings, session, redis, slots, prompts),
                    sql=_sql(settings, session),
                    embed=_embed(settings),
                )
            except Exception:  # one exam's error never stops the others; arq logs the tick
                log.exception("eval_advance_failed eval_run=%s", ev_id)
                await session.rollback()


def _judge(settings, session, redis, slots, prompts):
    from ffcore.runtime.adapters import LiteLLMModel
    from ffcore.services.quota import QuotaGate, Subject, engine_for

    guardrail = get_guardrail_settings()

    async def run_judge(run, item, facts, cfg):
        if not settings.eval_judge_model:
            return Score("llm_judge", None, None, "judge_model_not_configured", "error"), ""
        version = await session.get(AgentVersion, run.agent_version_id)
        definition = parse_definition(version.definition)
        policy = await resolve_policy(session, run.project_id, definition.guardrail_policy_key)
        guard = judge_mod.EgressGuard(
            session,
            redis,
            policy,
            run_id=run.id,
            project_id=run.project_id,
            egress_enabled=guardrail.guardrail_egress_enabled,
            ttl_s=guardrail.pii_token_ttl_s,
        )
        model = judge_mod.LiteLLMJudgeModel(
            LiteLLMModel(
                settings,
                session,
                slots,
                run_id=run.id,
                project_id=run.project_id,
                user_id=run.user_id,
                model_key=settings.eval_judge_model,
                job_class=JobClass.background,
                quota=QuotaGate(
                    engine_for(settings, redis),
                    redis,
                    session,
                    Subject(
                        project_id=str(run.project_id), user_id=str(run.user_id), api_key_id=None
                    ),
                    settings=settings,
                ),
            )
        )
        expected = item.get("expectedOutput") or {}
        try:
            result = await judge_mod.judge(
                question=item["input"]["message"],
                expected=str(
                    expected.get("answer") or ", ".join(expected.get("must_contain") or [])
                ),
                answer=facts.answer,
                rubric=judge_mod.PromptRubric(prompts),
                guard=guard,
                model=model,
                pass_min=int(cfg.get("pass_min", 4)),
            )
        except Exception as exc:  # model, quota or prompt failure: a coded item error
            code = getattr(exc, "code", None) or type(exc).__name__
            return Score("llm_judge", None, None, f"judge_failed:{code}", "error"), ""
        return result.score, result.reason

    return run_judge


def _sql(settings, session):
    from ffcore.services import mcp_client, mcp_tools

    async def reread(run, tool_key, sql_text):
        """The SQL the agent ran (after a person approved it), read again with the same tool
        and the exam starter's identity: the read-only database and the validator apply."""
        rows = await session.execute(
            select(Tool, ToolAction)
            .join(ToolAction, ToolAction.tool_id == Tool.id)
            .where(
                Tool.project_id == run.project_id,
                Tool.key == tool_key,
                Tool.deleted_at.is_(None),
                ToolAction.name == "run_sql",
            )
        )
        found = rows.first()
        if found is None:
            return None
        tool, action = found
        caller = mcp_client.Caller(user_id=str(run.user_id), project_id=str(run.project_id))
        result = await mcp_client.call(
            mcp_tools.target_of(tool, settings),
            action.name,
            {"sql": sql_text, "reason": "exam check"},
            settings,
            caller=caller,
            timeout_s=action.timeout_s,
        )
        await write_event(
            session,
            AuditEntry(
                action="eval_sql_check",
                resource_type="run",
                outcome="success",
                actor_type="service",
                actor_id="eval",
                project_id=str(run.project_id),
                resource_id=str(run.id),
                before=None,
                after={"tool_key": tool_key, "is_error": result.is_error},
                request_id="eval",
                ip=None,
            ),
        )
        if result.is_error:
            return None
        return parse_csv_rows(result.text)

    return reread


def _embed(settings):
    from ffcore.knowledge.ingest import HttpEmbedClient

    client = HttpEmbedClient(settings)

    async def embed(texts):
        return (await client.embed(texts)).dense

    return embed
