"""Start one run of a resolved agent version (06a, extracted for 09).

`POST /agents/{key}/runs` (api/runs.py) checks the caller and resolves the agent and version,
then calls `start_run`; the exam engine (09) calls the same function for each item, so an exam
run is an ordinary `channel=test` run with the same rows, audit event, first event and queue
job. Moved without a change in behaviour (K-09-0007 S7).
"""

from collections.abc import Awaitable, Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ffcore.api.common import invalid, not_found
from ffcore.core.config import Settings
from ffcore.models.agents import Agent, AgentVersion
from ffcore.models.runs import Conversation, Message, Run
from ffcore.runtime.contracts import RunStatus, TriggerType
from ffcore.runtime.definition import parse_definition
from ffcore.runtime.queue import RunQueue

AuditWriter = Callable[[AsyncSession, Run, AgentVersion], Awaitable[None]]
QueuedEvent = Callable[[AsyncSession, Settings, Run], Awaitable[None]]


async def start_run(
    session: AsyncSession,
    settings: Settings,
    queue: RunQueue,
    *,
    project_id: UUID,
    agent: Agent,
    version: AgentVersion,
    user_id: UUID,
    created_by: str,
    input: str,
    variables: dict[str, str],
    channel: str,
    conversation_id: UUID | None,
    audit: AuditWriter,
    queued_event: QueuedEvent,
) -> Run:
    """Insert the run (and its conversation and first message), audit it, commit, write the
    `queued` event and enqueue the job. Unknown variables and a foreign conversation are
    refused before anything is written."""
    definition = parse_definition(version.definition)
    unknown = sorted(set(variables) - {v.key for v in definition.variables})
    if unknown:
        raise invalid("variable_unknown", f"Unknown variables: {unknown}")

    if conversation_id is not None:
        conversation = await session.scalar(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.project_id == project_id,
                Conversation.agent_id == agent.id,
                Conversation.user_id == user_id,
                Conversation.deleted_at.is_(None),
            )
        )
        if conversation is None:
            raise not_found("conversation")
    else:
        conversation = Conversation(
            project_id=project_id,
            agent_id=agent.id,
            user_id=user_id,
            title=input[:80],
            created_by=created_by,
        )
        session.add(conversation)
        await session.flush()
    run = Run(
        project_id=project_id,
        agent_id=agent.id,
        agent_version_id=version.id,
        conversation_id=conversation.id,
        user_id=user_id,
        channel=channel,
        trigger_type=TriggerType.chat,
        status=RunStatus.queued,
        input=input,
        variables=variables,
        created_by=created_by,
    )
    session.add(run)
    await session.flush()
    session.add(Message(conversation_id=conversation.id, run_id=run.id, role="user", content=input))
    await audit(session, run, version)
    await session.commit()
    await queued_event(session, settings, run)
    await queue.enqueue(str(run.id))
    return run
